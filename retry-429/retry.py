"""Call an HTTP API and retry on 429/5xx, honouring Retry-After. Standard library only (Python 3.9+)."""
import email.utils
import json
import random
import time
import urllib.error
import urllib.request

RETRYABLE = {429, 500, 502, 503, 504}


def retry_after_seconds(value):
    """Retry-After is either a number of seconds or an HTTP date (RFC 9110, section 10.2.3)."""
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return int(value)
    try:
        when = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, when.timestamp() - time.time())


def post_json(url, payload, headers=None, max_attempts=5, base=0.5, cap=30.0):
    body = json.dumps(payload).encode()
    for attempt in range(1, max_attempts + 1):
        req = urllib.request.Request(url, data=body, method="POST",
                                     headers={"content-type": "application/json", **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as err:
            if err.code not in RETRYABLE or attempt == max_attempts:
                raise
            wait = retry_after_seconds(err.headers.get("Retry-After"))
            if wait is None:
                # Exponential backoff with full jitter: random value between 0 and base * 2^attempt, capped.
                wait = random.uniform(0, min(cap, base * 2 ** attempt))
            wait = min(wait, cap)
            print(f"HTTP {err.code}, attempt {attempt}/{max_attempts}, waiting {wait:.1f}s")
            time.sleep(wait)
