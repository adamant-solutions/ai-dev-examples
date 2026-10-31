# A REST API as an MCP server, with an allow-list (Python, MCP SDK 2.x)

Article: https://tools.adamant-solutions.com/blog/mcp-server-from-openapi/

- `openapi.json`: an OpenAPI 3.1 description of a small orders API with six operations (three reads, a refund, a delete, an export).
- `server.py`: a low-level MCP `Server` that turns only three allow-listed GET operations into tools. Input schemas come from the OpenAPI parameters with `additionalProperties: false`; arguments are validated with `jsonschema` before any HTTP call; path values are URL-encoded; the base URL and the API token belong to the server; responses are reduced to allow-listed fields; upstream errors are not forwarded; a simple rate limit.
- `fake_api.py`: a standard-library HTTP server that implements the API and records every request.
- `test_server.py`: tests with the official SDK `Client`, in memory and over Streamable HTTP: malicious and invalid arguments, operations outside the allow-list, leaked fields, upstream errors, rate limit. No API key, no network.

Versions checked on 2026-10-31 on PyPI: mcp 2.3.0 (protocol revision 2026-07-28), jsonschema 4.26.0, uvicorn 0.54.0. Python 3.10 or newer.

```bash
pip install -r requirements.txt
python -m unittest -v
```

Run it against your own API (localhost only, no MCP authorization configured):

```bash
ORDERS_API_URL=http://127.0.0.1:9000 ORDERS_API_TOKEN=... python server.py
# MCP endpoint: http://127.0.0.1:8000/mcp
```
