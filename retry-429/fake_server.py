"""Test server: answers 429 a few times (Retry-After in seconds, then as an HTTP date, then none), then 200."""
import email.utils, http.server, json, sys, time
plan = ["429:1", "429:date", "503:", "200"]
state = {"i": 0}
class H(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers.get("content-length", 0)))
        step = plan[min(state["i"], len(plan) - 1)]; state["i"] += 1
        if step == "200":
            body = json.dumps({"ok": True, "attempts": state["i"]}).encode()
            self.send_response(200); self.send_header("content-type", "application/json")
        else:
            code, ra = step.split(":")
            body = b'{"error":"rate_limited"}'
            self.send_response(int(code))
            if ra == "date": self.send_header("Retry-After", email.utils.formatdate(time.time() + 1, usegmt=True))
            elif ra: self.send_header("Retry-After", ra)
        self.send_header("content-length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass
if __name__ == "__main__":
    http.server.HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
