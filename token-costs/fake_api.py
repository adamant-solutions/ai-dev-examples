"""Local stand-in for the two token counting endpoints, so tests need no API key and cost nothing.

It does not tokenize anything: it returns a fixed count and remembers the last request it received.
"""
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

last = {}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def reply(self, status, obj):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # GET /last -> the last request, for assertions
        self.reply(200, last)

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["content-length"])))
        last.clear()
        last.update(path=self.path, body=req, headers={k.lower(): v for k, v in self.headers.items()})
        if self.path == "/v1/messages/count_tokens":
            self.reply(200, {"input_tokens": 42})
        elif self.path == "/v1/responses/input_tokens":
            self.reply(200, {"object": "response.input_tokens", "input_tokens": 17})
        else:
            self.reply(404, {"error": "not found"})


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), Handler).serve_forever()
