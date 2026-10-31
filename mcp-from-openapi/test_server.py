"""Tests with the official MCP Python SDK client against a fake REST API. No API key, no network."""
import json
import socket
import threading
import time
import unittest
from pathlib import Path

import uvicorn
from mcp import Client, MCPError
from mcp.types import TextContent

import fake_api
from server import RateLimiter, build_url, create_server, load_operations


def text(result) -> str:
    return "".join(b.text for b in result.content if isinstance(b, TextContent))


class InMemoryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.api = fake_api.start()
        self.base = f"http://127.0.0.1:{self.api.server_port}"
        self.server = create_server(self.base, fake_api.TOKEN)

    def tearDown(self):
        self.api.shutdown()
        self.api.server_close()

    async def test_only_allow_listed_read_only_tools_are_listed(self):
        async with Client(self.server, raise_exceptions=True) as client:
            tools = (await client.list_tools()).tools
        self.assertEqual([t.name for t in tools], ["getCustomer", "listOrders", "getOrder"])
        for tool in tools:
            self.assertTrue(tool.annotations.read_only_hint)
            self.assertFalse(tool.input_schema["additionalProperties"])

    async def test_call_returns_only_allowed_fields(self):
        async with Client(self.server, raise_exceptions=True) as client:
            result = await client.call_tool("getCustomer", {"customer_id": "C-0001"})
        self.assertFalse(result.is_error)
        self.assertEqual(json.loads(text(result)), {"id": "C-0001", "name": "Ada Rossi", "country": "IT"})
        # email, phone and the injected "internal_notes" never reach the model
        self.assertNotIn("Ignore all previous instructions", text(result))
        self.assertEqual(self.api.requests[-1]["authorization"], f"Bearer {fake_api.TOKEN}")

    async def test_query_parameters(self):
        async with Client(self.server, raise_exceptions=True) as client:
            result = await client.call_tool("listOrders", {"customer_id": "C-0001", "status": "shipped"})
        self.assertEqual(json.loads(text(result)),
                         [{"id": "A-1001", "status": "shipped", "total": 59.9, "currency": "EUR"}])
        self.assertEqual(self.api.requests[-1]["query"], "customer_id=C-0001&status=shipped")

    async def test_invalid_arguments_never_reach_the_api(self):
        bad_calls = [
            {"customer_id": "../admin/export"},                  # path traversal
            {"customer_id": "C-0001", "url": "http://evil.example"},  # extra argument
            {},                                                  # missing argument
            {"customer_id": 1},                                  # wrong type
        ]
        async with Client(self.server, raise_exceptions=True) as client:
            for args in bad_calls:
                result = await client.call_tool("getCustomer", args)
                self.assertTrue(result.is_error, args)
                self.assertIn("Invalid arguments", text(result))
            result = await client.call_tool("listOrders", {"customer_id": "C-0001", "limit": 1000})
            self.assertTrue(result.is_error)
        self.assertEqual(self.api.requests, [])

    async def test_operations_outside_the_allow_list_are_unknown_tools(self):
        async with Client(self.server, raise_exceptions=True) as client:
            for name in ["deleteCustomer", "refundOrder", "exportAllData"]:
                with self.assertRaises(MCPError) as ctx:
                    await client.call_tool(name, {"customer_id": "C-0001", "order_id": "A-1001"})
                self.assertIn("Unknown tool", str(ctx.exception))
        self.assertEqual(self.api.requests, [])

    async def test_upstream_errors_are_short_and_do_not_leak(self):
        async with Client(self.server, raise_exceptions=True) as client:
            missing = await client.call_tool("getOrder", {"order_id": "A-9999"})
            crash = await client.call_tool("getOrder", {"order_id": "A-9500"})
        self.assertTrue(missing.is_error)
        self.assertEqual(text(missing), "Not found. Check the id and try again.")
        self.assertTrue(crash.is_error)
        self.assertEqual(text(crash), "The orders API returned HTTP 500.")
        self.assertNotIn("hunter2", text(crash))

    async def test_rate_limit(self):
        server = create_server(self.base, fake_api.TOKEN, rate_limiter=RateLimiter(limit=2, window=60))
        async with Client(server, raise_exceptions=True) as client:
            results = [await client.call_tool("getOrder", {"order_id": "A-1001"}) for _ in range(3)]
        self.assertEqual([r.is_error for r in results], [False, False, True])
        self.assertEqual(len(self.api.requests), 2)


class UnitTests(unittest.TestCase):
    def test_build_url_encodes_path_values(self):
        op = load_operations(json.loads(Path("openapi.json").read_text()))["getCustomer"]
        # Even if validation were skipped, the value stays inside one path segment.
        self.assertEqual(build_url("http://api.local", op, {"customer_id": "../admin/export"}),
                         "http://api.local/customers/..%2Fadmin%2Fexport")

    def test_rate_limiter_window(self):
        now = [0.0]
        limiter = RateLimiter(limit=1, window=10, clock=lambda: now[0])
        self.assertTrue(limiter.allow())
        self.assertFalse(limiter.allow())
        now[0] = 10.0
        self.assertTrue(limiter.allow())


class StreamableHttpTest(unittest.IsolatedAsyncioTestCase):
    """The same server over Streamable HTTP, the transport you deploy."""

    async def test_over_http(self):
        api = fake_api.start()
        server = create_server(f"http://127.0.0.1:{api.server_port}", fake_api.TOKEN)
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        config = uvicorn.Config(server.streamable_http_app(host="127.0.0.1"), host="127.0.0.1",
                                port=port, log_level="warning")
        web = uvicorn.Server(config)
        thread = threading.Thread(target=web.run, daemon=True)
        thread.start()
        try:
            for _ in range(100):
                if web.started:
                    break
                time.sleep(0.05)
            async with Client(f"http://127.0.0.1:{port}/mcp") as client:
                result = await client.call_tool("getOrder", {"order_id": "A-1001"})
            self.assertFalse(result.is_error)
            self.assertEqual(json.loads(text(result))["status"], "shipped")
            self.assertNotIn("card_last4", text(result))
        finally:
            web.should_exit = True
            thread.join(timeout=5)
            api.shutdown()
            api.server_close()


if __name__ == "__main__":
    unittest.main()
