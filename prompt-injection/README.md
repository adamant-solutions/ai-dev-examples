# Prompt injection: defenses you can test (Python, JavaScript)

Article: https://tools.adamant-solutions.com/blog/prompt-injection-defenses/

- `defenses.py` (standard library only):
  1. a system prompt that states the policy, and `untrusted_tool_result()` that returns third-party text JSON-encoded inside a `tool_result` block, never in the system prompt;
  2. a per-task tool allow-list, strict argument checks that act with the signed-in user's permissions, and human confirmation for refunds and emails (the confirmation text is built by code, not by the model);
  3. `parse_triage()`: strict validation of the model's JSON output;
  4. `looks_like_injection()`: a keyword filter, with tests that show how easily it is bypassed.
- `safe_markdown.mjs`: removes links and images to unknown hosts from a model's Markdown answer before rendering (image-based data exfiltration).
- `test_defenses.py`, `safe_markdown.test.mjs`: malicious inputs against every defense. No model, no API key.

No technique here stops prompt injection. Together they limit what a successful injection can do.

Checked on 2026-10-31: Python 3.12 standard library, Node.js 22 (`node:test`), no third-party packages.

```bash
python -m unittest -v
node --test
```
