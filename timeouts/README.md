# Timeouts and cancellation for model calls (Python httpx, Node.js fetch)

Article: https://tools.adamant-solutions.com/blog/llm-timeouts-cancellation/

Versions checked on 2026-11-10: httpx 0.28.1 (PyPI), Python 3.11+ (`asyncio.timeout`), Node.js 20.3+ (`AbortSignal.any`; tested with 22).

```bash
pip install -r requirements.txt
python3 -m unittest -v     # httpx client against fake_server.py
node --test                # fetch client against fake_server.py
```

`fake_server.py` is a local server with no API key: `/drip` streams a token every 0.1 s forever, `/stall` sends one line and then goes silent, `/stats` counts the streams the client abandoned. The tests check that a total deadline, an idle/read timeout and a caller-side cancel each end the call, and that the server really sees the connection close.

The connect timeout is configured in the code but not tested (it needs a black-holed address, which is not reliable in CI).
