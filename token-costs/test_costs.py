"""python -m unittest -v  (needs: pip install -r requirements.txt ; npm ci). No API key, no network calls to providers."""
import json
import subprocess
import threading
import unittest
from http.server import ThreadingHTTPServer
from types import SimpleNamespace

import anthropic
import openai

import fake_api
from costs import (PRICES, BudgetExceeded, actual_cost, check_budget, count_claude, count_openai,
                   count_tiktoken, estimate_cost)

SAMPLES = {
    "en": "Count the tokens before you call the model, then compare with the usage the API returns.",
    "it": "Conta i token prima di chiamare il modello, poi confrontali con l'uso restituito dall'API.",
    "code": 'def add(a: int, b: int) -> int:\n    return a + b  # 🙂\n',
}


def node(script):
    return json.loads(subprocess.run(["node", "--input-type=module", "-e", script], check=True,
                                     capture_output=True, text=True).stdout)


class Costs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), fake_api.Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_python_and_javascript_tokenizers_agree(self):
        py = {k: count_tiktoken(v) for k, v in SAMPLES.items()}
        js = node("import {countTiktoken} from './costs.mjs';"
                  f"const s={json.dumps(SAMPLES)};"
                  "console.log(JSON.stringify(Object.fromEntries(Object.entries(s).map(([k,v])=>[k,countTiktoken(v)]))))")
        self.assertEqual(py, js)
        print("\n  o200k_base counts:", py)

    def test_estimate_and_budget(self):
        p = PRICES["claude-sonnet-5-5"]
        low, high = estimate_cost(12_000, 1_000, p)
        self.assertAlmostEqual(low, 0.024)
        self.assertAlmostEqual(high, 0.034)
        self.assertAlmostEqual(check_budget(12_000, 1_000, p, max_usd=0.05), 0.034)
        with self.assertRaises(BudgetExceeded):
            check_budget(12_000, 1_000, p, max_usd=0.03)

    def test_actual_cost_with_cache(self):
        usage = SimpleNamespace(input_tokens=200, cache_creation_input_tokens=0,
                                cache_read_input_tokens=10_000, output_tokens=500)
        # 200*2 + 10000*0.10 + 500*10 = 400 + 1000 + 5000 = 6400 / 1e6
        self.assertAlmostEqual(actual_cost(usage, PRICES["claude-sonnet-5-5"]), 0.0064)

    def test_count_claude_with_sdk(self):
        client = anthropic.Anthropic(api_key="test-key", base_url=self.base)
        n = count_claude(client, "claude-sonnet-5-5", [{"role": "user", "content": "Hello"}], system="Be brief")
        self.assertEqual(n, 42)
        last = fake_api.last  # the fake server runs in this process
        self.assertEqual(last["path"], "/v1/messages/count_tokens")
        h = last["headers"]
        self.assertTrue(h.get("x-api-key") == "test-key" or h.get("authorization") == "Bearer test-key")
        self.assertIn("anthropic-version", last["headers"])
        self.assertEqual(last["body"]["system"], "Be brief")

    def test_count_openai_with_sdk(self):
        client = openai.OpenAI(api_key="test-key", base_url=f"{self.base}/v1")
        self.assertEqual(count_openai(client, "gpt-5", "Hello"), 17)
        self.assertEqual(fake_api.last["path"], "/v1/responses/input_tokens")
        self.assertEqual(fake_api.last["body"], {"model": "gpt-5", "input": "Hello"})

    def test_count_claude_with_fetch(self):
        n = node("import {countClaudeTokens} from './costs.mjs';"
                 f"console.log(await countClaudeTokens({{model:'claude-opus-5-5',apiKey:'k',baseUrl:'{self.base}',"
                 "messages:[{role:'user',content:'Hello'}]}))")
        self.assertEqual(n, 42)
        self.assertEqual(fake_api.last["headers"]["anthropic-version"], "2023-06-01")
        self.assertEqual(fake_api.last["body"]["model"], "claude-opus-5-5")


if __name__ == "__main__":
    unittest.main()
