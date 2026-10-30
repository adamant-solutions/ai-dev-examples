# Count tokens and estimate costs before calling a model (Python, JavaScript)

Article: https://tools.adamant-solutions.com/blog/count-tokens-costs/

- `costs.py`: local count with `tiktoken` (OpenAI encodings), exact counts from Anthropic's `count_tokens` and OpenAI's `responses.input_tokens` endpoints, cost range, budget check, real cost from `usage`.
- `costs.mjs`: the same local count with `js-tiktoken`, the cost range, and `count_tokens` with plain `fetch`.

Versions checked on 2026-10-30: tiktoken 0.14.0, anthropic 2.3.0, openai 3.41.0 (PyPI); js-tiktoken 1.0.21 (npm). Prices in the code come from https://platform.claude.com/docs/en/about-claude/pricing on the same day: check them again before you rely on them.

```bash
pip install -r requirements.txt
npm ci
python -m unittest -v      # no API key: fake_api.py stands in for the counting endpoints
```

The first `tiktoken` call downloads the encoding file and caches it (set `TIKTOKEN_CACHE_DIR` to choose where). `js-tiktoken` ships the ranks in the package.
