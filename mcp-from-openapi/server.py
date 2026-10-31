"""Expose a few read-only operations of a REST API, described by an OpenAPI file, as MCP tools.

Low-level MCP Server (mcp 2.x): the tool schemas come from the OpenAPI file, so we write them
ourselves, and we validate the arguments ourselves (the low-level server does not).
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from pathlib import Path

import anyio
from jsonschema import Draft202012Validator
from mcp import MCPError
from mcp.server import Server, ServerRequestContext
from mcp.types import (INVALID_PARAMS, CallToolRequestParams, CallToolResult, ListToolsResult,
                       PaginatedRequestParams, TextContent, Tool, ToolAnnotations)

# The allow-list: which operations become tools, and which response fields the model may see.
# Anything not listed here (refunds, deletes, exports, new endpoints added later) is not exposed.
ALLOWED_OPERATIONS = {
    "getCustomer": ["id", "name", "country"],
    "listOrders": ["id", "status", "total", "currency"],
    "getOrder": ["id", "customer_id", "status", "total", "currency", "eta"],
}
MAX_RESPONSE_BYTES = 64_000
UPSTREAM_TIMEOUT_SECONDS = 5


def load_operations(spec: dict) -> dict[str, dict]:
    """Index the OpenAPI operations by operationId."""
    operations = {}
    for path, item in spec["paths"].items():
        for method, op in item.items():
            if method in ("get", "post", "put", "patch", "delete"):
                operations[op["operationId"]] = {**op, "method": method.upper(), "path": path}
    return operations


def build_tool(op_id: str, op: dict) -> Tool:
    """Turn one allow-listed GET operation into an MCP tool with a strict input schema."""
    if op["method"] != "GET":
        raise ValueError(f"{op_id}: only read-only GET operations are exposed by this server")
    properties, required = {}, []
    for param in op.get("parameters", []):
        if param["in"] not in ("path", "query"):
            raise ValueError(f"{op_id}: parameter location {param['in']!r} is not supported")
        properties[param["name"]] = {**param["schema"], "description": param.get("description", "")}
        if param.get("required"):
            required.append(param["name"])
    schema = {"type": "object", "properties": properties, "required": required,
              "additionalProperties": False}
    Draft202012Validator.check_schema(schema)
    return Tool(
        name=op_id,
        description=f"{op['summary']} Read-only. Returns only these fields: "
                    f"{', '.join(ALLOWED_OPERATIONS[op_id])}.",
        input_schema=schema,
        annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
    )


def build_url(base_url: str, op: dict, args: dict) -> str:
    """Fill path and query parameters. The base URL is fixed: the model can never choose the host."""
    path, query = op["path"], {}
    for param in op.get("parameters", []):
        if param["name"] not in args:
            continue
        value = args[param["name"]]
        if param["in"] == "path":
            path = path.replace("{" + param["name"] + "}", urllib.parse.quote(str(value), safe=""))
        else:
            query[param["name"]] = value
    return base_url.rstrip("/") + path + ("?" + urllib.parse.urlencode(query) if query else "")


def keep_fields(data, fields: list[str]):
    """Drop every field that is not explicitly allowed (emails, notes, card data...)."""
    if isinstance(data, list):
        return [keep_fields(item, fields) for item in data]
    if isinstance(data, dict):
        return {k: v for k, v in data.items() if k in fields}
    return data


class RateLimiter:
    """At most `limit` calls in any `window` seconds (per server process)."""

    def __init__(self, limit: int, window: float, clock=time.monotonic):
        self.limit, self.window, self.clock, self.calls = limit, window, clock, deque()

    def allow(self) -> bool:
        now = self.clock()
        while self.calls and now - self.calls[0] >= self.window:
            self.calls.popleft()
        if len(self.calls) >= self.limit:
            return False
        self.calls.append(now)
        return True


def error(text: str) -> CallToolResult:
    """A tool execution error: the model reads the text and can correct its call."""
    return CallToolResult(content=[TextContent(type="text", text=text)], is_error=True)


def create_server(base_url: str, api_token: str, spec_path: str = "openapi.json",
                  rate_limiter: RateLimiter | None = None) -> Server:
    spec = json.loads((Path(__file__).parent / spec_path).read_text())
    operations = load_operations(spec)
    tools = {op_id: build_tool(op_id, operations[op_id]) for op_id in ALLOWED_OPERATIONS}
    validators = {name: Draft202012Validator(tool.input_schema) for name, tool in tools.items()}
    limiter = rate_limiter or RateLimiter(limit=30, window=60)

    def fetch(url: str):
        # The API credential belongs to this server. It never comes from the model or the client.
        request = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_token}",
                                                       "Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=UPSTREAM_TIMEOUT_SECONDS) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            raise ValueError("response too large")
        return json.loads(body)

    async def list_tools(ctx: ServerRequestContext, params: PaginatedRequestParams | None) -> ListToolsResult:
        return ListToolsResult(tools=list(tools.values()))

    async def call_tool(ctx: ServerRequestContext, params: CallToolRequestParams) -> CallToolResult:
        if params.name not in tools:
            raise MCPError(INVALID_PARAMS, f"Unknown tool: {params.name}")
        args = params.arguments or {}
        problems = sorted(validators[params.name].iter_errors(args), key=lambda e: list(e.path))
        if problems:
            return error("Invalid arguments: " + "; ".join(
                f"{'/'.join(map(str, p.path)) or 'arguments'}: {p.message}" for p in problems))
        if not limiter.allow():
            return error("Rate limit reached for this server. Try again in a minute.")
        url = build_url(base_url, operations[params.name], args)
        try:
            data = await anyio.to_thread.run_sync(fetch, url)
        except urllib.error.HTTPError as e:
            # Do not forward the upstream error body: it can contain internals.
            if e.code == 404:
                return error("Not found. Check the id and try again.")
            return error(f"The orders API returned HTTP {e.code}.")
        except (urllib.error.URLError, TimeoutError, ValueError):
            return error("The orders API is not available or sent an invalid response.")
        data = keep_fields(data, ALLOWED_OPERATIONS[params.name])
        return CallToolResult(content=[TextContent(type="text", text=json.dumps(data))])

    return Server("orders-api", version="1.0.0", on_list_tools=list_tools, on_call_tool=call_tool)


if __name__ == "__main__":
    import uvicorn

    server = create_server(os.environ["ORDERS_API_URL"], os.environ["ORDERS_API_TOKEN"])
    # host="127.0.0.1" also turns on the SDK's DNS rebinding protection (Host/Origin checks).
    uvicorn.run(server.streamable_http_app(host="127.0.0.1"), host="127.0.0.1", port=8000)
