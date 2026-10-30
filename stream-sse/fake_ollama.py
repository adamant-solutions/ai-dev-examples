"""Minimal stand-in for Ollama's POST /api/chat (streaming NDJSON), for tests without a model.

GET /stats returns how many streams the client closed before the end (to test cancellation).
Model "missing" answers 404, like Ollama does for a model that is not pulled.
"""
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

WORDS = ["Light ", "is ", "scattered ", "by ", "the ", "air.\n", "Blue ", "scatters ", "more."]
stats = {"completed": 0, "client_closed": 0}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def do_GET(self):
        body = json.dumps(stats).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["content-length"])))
        if req.get("model") == "missing":
            body = b'{"error":"model \'missing\' not found"}'
            self.send_response(404)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        delay = 0.3 if "slow" in req["messages"][-1]["content"] else 0.01
        self.send_response(200)
        self.send_header("content-type", "application/x-ndjson")
        self.send_header("transfer-encoding", "chunked")
        self.end_headers()
        chunks = [{"message": {"role": "assistant", "content": w}, "done": False} for w in WORDS]
        chunks.append({"message": {"role": "assistant", "content": ""}, "done": True,
                       "prompt_eval_count": 12, "eval_count": len(WORDS)})
        try:
            for c in chunks:
                data = (json.dumps(c) + "\n").encode()
                self.wfile.write(b"%x\r\n%s\r\n" % (len(data), data))
                self.wfile.flush()
                time.sleep(delay)
            self.wfile.write(b"0\r\n\r\n")
            stats["completed"] += 1
        except (BrokenPipeError, ConnectionResetError):
            stats["client_closed"] += 1


class Server(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        pass  # idle keep-alive connections reset by the client are expected here


if __name__ == "__main__":
    Server(("127.0.0.1", int(sys.argv[1])), Handler).serve_forever()
