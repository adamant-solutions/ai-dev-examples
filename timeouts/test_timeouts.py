import asyncio
import json
import unittest
import urllib.request

import httpx

import client
import fake_server


def abandoned(base):
    with urllib.request.urlopen(base + "/stats") as r:
        return json.load(r)["abandoned"]


async def wait_for_abandoned(base, expected, seconds=5):
    for _ in range(seconds * 10):
        if abandoned(base) >= expected:
            return True
        await asyncio.sleep(0.1)
    return False


class TimeoutTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = fake_server.serve()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    async def test_total_deadline_stops_a_stream_that_never_ends(self):
        before = abandoned(self.base)
        got = []
        # Tokens keep arriving every 0.1 s, so the read timeout (30 s) never fires.
        with self.assertRaises(TimeoutError):
            await client.stream_completion(f"{self.base}/drip", {}, total_deadline=1.0, on_token=got.append)
        self.assertGreater(len(got), 3)  # it did receive tokens before the deadline
        self.assertTrue(await wait_for_abandoned(self.base, before + 1), "server never saw the disconnect")

    async def test_read_timeout_fires_when_upstream_goes_quiet(self):
        original = client.TIMEOUTS
        client.TIMEOUTS = httpx.Timeout(connect=2.0, read=0.5, write=2.0, pool=2.0)
        try:
            with self.assertRaises(httpx.ReadTimeout):
                await client.stream_completion(f"{self.base}/stall", {}, total_deadline=10.0, on_token=lambda _: None)
        finally:
            client.TIMEOUTS = original

    async def test_task_cancel_closes_the_connection(self):
        before = abandoned(self.base)
        task = asyncio.create_task(client.stream_completion(f"{self.base}/drip", {}, on_token=lambda _: None))
        await asyncio.sleep(0.5)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(await wait_for_abandoned(self.base, before + 1), "server never saw the disconnect")


if __name__ == "__main__":
    unittest.main()
