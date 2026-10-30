# Stream a model's answer to the browser with Server-Sent Events (FastAPI + fetch)

Article: https://tools.adamant-solutions.com/blog/stream-llm-sse-browser/

- `server.py`: FastAPI endpoint `POST /api/chat/stream` that reads Ollama's streaming `/api/chat` (one JSON object per line) and re-sends it as SSE events `token`, `done` and `error`, using `fastapi.sse.EventSourceResponse`.
- `static/sse-client.js`: browser code (also runs in Node.js 18+) that reads `text/event-stream` from `fetch()` with a POST body, following the WHATWG parsing rules, and stops with an `AbortController`.
- `static/index.html`: a minimal page with Send and Stop buttons.

Versions checked on 2026-10-30 (PyPI): fastapi 0.162.0 (SSE support since 0.135.0), uvicorn 0.54.0, httpx 0.28.1. Python 3.10+.

```bash
pip install -r requirements.txt
ollama pull llama3.2                      # or set OLLAMA_MODEL to a model you already have
uvicorn server:app --port 8000            # open http://localhost:8000/
./test_stream.sh                          # no model needed: uses fake_ollama.py
```

The test starts a fake Ollama, runs the browser client in Node.js and checks: parsing of split chunks and CR/LF variants, the full answer, an upstream 404 reported as an `error` event, and that pressing Stop closes the connection to the model server.
