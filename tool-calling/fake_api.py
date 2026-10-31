"""A tiny stand-in for POST /v1/messages (Anthropic) and POST /v1/responses (OpenAI).

It answers in each provider's documented tool-calling format, so the official SDKs parse the
responses as usual. Rules: if the request has no tool results yet, ask for get_order_status once
per order id found in the question (A-1234); once the results are there, reply with text that
quotes them. A question containing "loop" always gets another tool call.
"""
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


def _order_ids(text: str) -> list[str]:
    return re.findall(r"A-\d{4}", text) or ["A-1001"]


def anthropic_reply(body: dict) -> dict:
    question = body["messages"][0]["content"]
    last = body["messages"][-1]["content"]
    results = [b for b in last if isinstance(b, dict) and b.get("type") == "tool_result"] \
        if isinstance(last, list) else []
    if results and "loop" not in question:
        summary = " | ".join(("ERROR " if r.get("is_error") else "") + r["content"] for r in results)
        content, stop = [{"type": "text", "text": f"Results: {summary}"}], "end_turn"
    else:
        content = [{"type": "text", "text": "Let me check."}] + [
            {"type": "tool_use", "id": f"toolu_fake_{i}", "name": "get_order_status",
             "input": {"order_id": oid}} for i, oid in enumerate(_order_ids(question))]
        stop = "tool_use"
    return {"id": "msg_fake", "type": "message", "role": "assistant", "model": body["model"],
            "content": content, "stop_reason": stop, "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 5}}


def openai_reply(body: dict) -> dict:
    question = body["input"][0]["content"]
    outputs = [i for i in body["input"] if i.get("type") == "function_call_output"]
    if outputs and "loop" not in question:
        text = "Results: " + " | ".join(o["output"] for o in outputs)
        output = [{"type": "message", "id": "msg_fake", "role": "assistant", "status": "completed",
                   "content": [{"type": "output_text", "text": text, "annotations": []}]}]
    else:
        output = [{"type": "function_call", "id": f"fc_fake_{i}", "call_id": f"call_fake_{i}",
                   "name": "get_order_status", "arguments": json.dumps({"order_id": oid}),
                   "status": "completed"} for i, oid in enumerate(_order_ids(question))]
    return {"id": "resp_fake", "object": "response", "created_at": 0, "model": body["model"],
            "status": "completed", "output": output, "parallel_tool_calls": True,
            "tool_choice": "auto", "tools": body.get("tools", []),
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}}


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.requests.append({"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()}, "body": body})
        if self.path == "/v1/messages":
            out = anthropic_reply(body)
        elif self.path == "/v1/responses":
            out = openai_reply(body)
        else:
            self.send_error(404)
            return
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def start() -> HTTPServer:
    server = HTTPServer(("127.0.0.1", 0), Handler)
    server.requests = []
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
