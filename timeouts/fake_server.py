"""Local fake model server for the timeout tests. No API key, no network.

GET/POST /drip   one line ("token N") every 0.1 s, forever (a stream that never ends)
GET/POST /stall  one line, then silence for 30 s (a stuck upstream)
GET      /stats  JSON with the number of streams the server saw abandoned by the client
"""
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

lock = threading.Lock()
stats = {"abandoned": 0}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"  # no chunking: the body ends when the socket closes

    def log_message(self, *args):
        pass

    def _stream(self, stall):
        self.send_response(200)
        self.send_header("content-type", "text/plain")
        self.end_headers()
        try:
            n = 0
            while True:
                n += 1
                self.wfile.write(f"token {n}\n".encode())
                self.wfile.flush()
                if stall:
                    time.sleep(30)
                    return
                time.sleep(0.1)
        except (BrokenPipeError, ConnectionResetError):
            with lock:
                stats["abandoned"] += 1

    def do_GET(self):
        if self.path == "/stats":
            with lock:
                body = json.dumps(stats).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self._stream(self.path == "/stall")

    do_POST = do_GET


def serve(port=0):
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


if __name__ == "__main__":
    s = serve(int(sys.argv[1]) if len(sys.argv) > 1 else 8400)
    print("listening on", s.server_address[1], flush=True)
    threading.Event().wait()
