"""Relays a streaming chat answer from Ollama to the browser as Server-Sent Events.

Run:  uvicorn server:app --port 8000   (then open http://localhost:8000/)
Env:  OLLAMA_URL (default http://localhost:11434), OLLAMA_MODEL (default llama3.2)
"""
import json
import os
from collections.abc import AsyncIterable

import httpx
from fastapi import FastAPI
from fastapi.sse import EventSourceResponse, ServerSentEvent
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")

app = FastAPI()
http = httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=120.0))


class Prompt(BaseModel):
    text: str


@app.post("/api/chat/stream", response_class=EventSourceResponse)
async def chat_stream(prompt: Prompt) -> AsyncIterable[ServerSentEvent]:
    body = {"model": MODEL, "messages": [{"role": "user", "content": prompt.text}], "stream": True}
    try:
        async with http.stream("POST", f"{OLLAMA_URL}/api/chat", json=body) as upstream:
            if upstream.status_code != 200:
                detail = (await upstream.aread()).decode(errors="replace")[:300]
                yield ServerSentEvent(data={"status": upstream.status_code, "detail": detail}, event="error")
                return
            async for line in upstream.aiter_lines():  # Ollama streams one JSON object per line
                if not line:
                    continue
                chunk = json.loads(line)
                if chunk.get("done"):
                    yield ServerSentEvent(data={"prompt_tokens": chunk.get("prompt_eval_count"),
                                                "output_tokens": chunk.get("eval_count")}, event="done")
                    return
                text = chunk.get("message", {}).get("content", "")
                if text:
                    yield ServerSentEvent(data={"text": text}, event="token")
    except httpx.HTTPError as exc:
        yield ServerSentEvent(data={"detail": type(exc).__name__}, event="error")


app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static"), html=True))
