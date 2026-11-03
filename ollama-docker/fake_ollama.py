"""Fake Ollama server for tests: answers /api/generate with fixed numbers and records requests."""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        self.server.requests.append((self.path, body))
        if "prompt" not in body:   # empty request = preload
            out = {"model": body["model"], "response": "", "done": True, "done_reason": "load"}
        else:
            first = len(self.server.requests) == 1   # first real call pays the model load
            out = {"model": body["model"], "response": "ok", "done": True,
                   "total_duration": 12_000_000_000 if first else 4_000_000_000,
                   "load_duration": 8_000_000_000 if first else 50_000_000,
                   "prompt_eval_count": 20, "prompt_eval_duration": 1_000_000_000,
                   "eval_count": 40, "eval_duration": 8_000_000_000}
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def start():
    server = HTTPServer(("127.0.0.1", 0), Handler)
    server.requests = []
    Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}"
