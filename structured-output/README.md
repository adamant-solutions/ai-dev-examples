# Structured output from a model: JSON schema, validation, bounded retry (Python, pydantic)

Article: https://tools.adamant-solutions.com/blog/structured-output-validation/

Versions checked on 2026-11-17: pydantic 2.14.3 (PyPI, released 2026-11-05), Python 3.10+ (tested with 3.11 and 3.12).

```bash
pip install -r requirements.txt
python -m unittest -v
```

- `extract.py`: a strict pydantic model (`Ticket`), `strip_fence`, `feedback` (validation errors as text for the model, without the input values), `extract` (ask, validate, send the errors back, at most N attempts) and `schema_for_provider`.
- `fake_model.py`: a scripted stand-in for a model, so the tests need no API key and no network.
- `test_extract.py`: lax vs strict, extra fields, enum and range errors, truncated JSON, duplicate keys, the generated JSON Schema, and the retry loop.

`extract()` takes any function `call_model(messages) -> str`, so you can wrap the SDK of your provider around it. No provider API is called by this example.
