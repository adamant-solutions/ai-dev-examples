# Tool (function) calling with a loop you can read (Python)

Article: https://tools.adamant-solutions.com/blog/tool-calling-basics/

- `tool_calling.py`: one tool (`get_order_status`) described once with a JSON Schema, a `run_tool` dispatcher that returns errors instead of raising, and two manual loops with a step limit: Anthropic Messages API (`tool_use` / `tool_result` blocks) and OpenAI Responses API (`function_call` / `function_call_output` items).
- `fake_api.py`: a standard-library HTTP server that answers `POST /v1/messages` and `POST /v1/responses` in each provider's documented tool-calling format.
- `test_tool_calling.py`: runs the official SDKs against the fake server: parallel calls, a failing tool, the step limit. No API key, no cost.

Versions checked on 2026-10-31: anthropic 2.3.0 and openai 3.42.0 on PyPI.

```bash
pip install -r requirements.txt
python -m unittest -v
```

The same `ask_openai` loop also runs against a local model through Ollama's OpenAI-compatible endpoint (`openai.OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")`); see the article for what a 1B model does with it.
