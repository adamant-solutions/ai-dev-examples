# Retry on HTTP 429 with backoff and Retry-After (Python, Node.js, Java)

Article: https://tools.adamant-solutions.com/blog/retry-429-retry-after/

No dependencies: Python 3.9+, Node.js 18+, Java 11+ (`java RetryClient.java` runs a single-file program).

```bash
./test_retry.sh   # runs the three clients against fake_server.py (429 -> 429 -> 503 -> 200)
```

`fake_server.py` answers 429 with `Retry-After` in seconds, then 429 with `Retry-After` as an HTTP date, then 503 without it, then 200.
