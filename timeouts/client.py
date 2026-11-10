import asyncio

import httpx

# Four separate limits. "read" is the longest silence allowed between two chunks,
# not the time for the whole answer.
TIMEOUTS = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)


async def stream_completion(url, payload, total_deadline=120.0, on_token=print):
    """Stream lines from a model endpoint with a per-chunk timeout AND a total deadline.

    Leaving the `async with` blocks (deadline, error or task.cancel()) closes the
    connection, which is the signal the server needs to stop generating.
    """
    tokens = []
    async with httpx.AsyncClient(timeout=TIMEOUTS) as client:
        async with asyncio.timeout(total_deadline):  # Python 3.11+
            async with client.stream("POST", url, json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    tokens.append(line)
                    on_token(line)
    return tokens
