"""Runs the official anthropic and openai SDKs against fake_api.py: no API key, no cost."""
import json
import unittest

import anthropic
import openai

import fake_api
from tool_calling import StepLimitExceeded, ask_claude, ask_openai, run_tool


class ToolCallingTest(unittest.TestCase):
    def setUp(self):
        self.server = fake_api.start()
        base = f"http://127.0.0.1:{self.server.server_port}"
        self.claude = anthropic.Anthropic(api_key="test-key", base_url=base, max_retries=0)
        self.oai = openai.OpenAI(api_key="test-key", base_url=f"{base}/v1", max_retries=0)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def test_run_tool_errors_are_returned_not_raised(self):
        self.assertEqual(run_tool("get_order_status", {"order_id": "A-9999"}),
                         ("LookupError: no order with id A-9999", True))
        self.assertEqual(run_tool("delete_everything", {}), ("unknown tool: delete_everything", True))
        self.assertTrue(run_tool("get_order_status", {"id": "A-1001"})[1])  # wrong argument name

    def test_claude_parallel_calls_and_error(self):
        answer = ask_claude(self.claude, "claude-sonnet-5-5", "Where are A-1001 and A-9999?")
        self.assertIn('"carrier": "DHL"', answer)
        self.assertIn("ERROR LookupError: no order with id A-9999", answer)
        first, second = [r["body"] for r in self.server.requests]
        tool = first["tools"][0]
        self.assertEqual((tool["name"], tool["strict"]), ("get_order_status", True))
        self.assertEqual(tool["input_schema"]["required"], ["order_id"])
        # second request: question, assistant turn with both tool_use blocks, ONE user message with both results
        self.assertEqual([m["role"] for m in second["messages"]], ["user", "assistant", "user"])
        self.assertEqual([b["type"] for b in second["messages"][1]["content"]], ["text", "tool_use", "tool_use"])
        results = second["messages"][2]["content"]
        self.assertEqual([r["tool_use_id"] for r in results], ["toolu_fake_0", "toolu_fake_1"])
        self.assertEqual([r["is_error"] for r in results], [False, True])

    def test_openai_function_call_round_trip(self):
        answer = ask_openai(self.oai, "gpt-6-astra", "Status of A-1002?")
        self.assertIn('"status": "processing"', answer)
        first, second = [r["body"] for r in self.server.requests]
        self.assertEqual(first["tools"][0]["type"], "function")
        self.assertEqual(first["tools"][0]["parameters"]["additionalProperties"], False)
        call, output = second["input"][1], second["input"][2]
        self.assertEqual((call["type"], call["call_id"]), ("function_call", "call_fake_0"))
        self.assertEqual((output["type"], output["call_id"]), ("function_call_output", "call_fake_0"))
        self.assertEqual(json.loads(output["output"])["order_id"], "A-1002")
        self.assertEqual(self.server.requests[0]["headers"]["authorization"], "Bearer test-key")

    def test_step_limit_stops_endless_tool_loops(self):
        with self.assertRaises(StepLimitExceeded):
            ask_claude(self.claude, "claude-sonnet-5-5", "loop on A-1001", max_steps=3)
        self.assertEqual(len(self.server.requests), 3)
        with self.assertRaises(StepLimitExceeded):
            ask_openai(self.oai, "gpt-6-astra", "loop on A-1001", max_steps=2)


if __name__ == "__main__":
    unittest.main()
