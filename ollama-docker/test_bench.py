import unittest

import bench
import fake_ollama


class BenchTest(unittest.TestCase):
    def setUp(self):
        self.server, self.url = fake_ollama.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def test_summarize_units(self):
        s = bench.summarize(bench.generate(self.url, "m", "hi"))
        self.assertEqual(s["load_s"], 8.0)
        self.assertEqual(s["output_tokens_per_s"], 5.0)    # 40 tokens / 8 s
        self.assertEqual(s["prompt_tokens_per_s"], 20.0)   # 20 tokens / 1 s

    def test_generate_request_shape(self):
        bench.generate(self.url, "m", "hi", num_predict=10)
        path, body = self.server.requests[0]
        self.assertEqual(path, "/api/generate")
        self.assertIs(body["stream"], False)
        self.assertEqual(body["options"], {"num_predict": 10})

    def test_preload_sends_no_prompt(self):
        bench.preload(self.url, "m", "1h")
        _, body = self.server.requests[0]
        self.assertNotIn("prompt", body)
        self.assertEqual(body["keep_alive"], "1h")

    def test_zero_duration_gives_none(self):
        self.assertIsNone(bench.summarize({"eval_count": 5, "eval_duration": 0})["output_tokens_per_s"])

    def test_cold_slower_than_warm(self):
        cold = bench.summarize(bench.generate(self.url, "m", "hi"))
        warm = bench.summarize(bench.generate(self.url, "m", "hi"))
        self.assertGreater(cold["load_s"], warm["load_s"])


if __name__ == "__main__":
    unittest.main()
