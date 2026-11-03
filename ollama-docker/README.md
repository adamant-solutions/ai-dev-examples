# Ollama in Docker on a CPU-only server (Python, no dependencies)

Article: https://tools.adamant-solutions.com/blog/ollama-docker-cpu/

- `compose.yaml`: Ollama in Docker without GPU, image pinned, models in a named volume, port bound to localhost, keep-alive, parallelism, queue and memory limit.
- `bench.py`: measures load time, prompt speed and generation speed from the fields Ollama returns (`load_duration`, `prompt_eval_*`, `eval_*`), cold and warm. Also has `preload()`.
- `fake_ollama.py` + `test_bench.py`: tests against a fake server, no model and no Docker needed.

Versions checked on 2026-11-03: Ollama 0.40.14 (Docker Hub tag `ollama/ollama:0.40.14`, pushed the same day). Python 3.12 in CI.
`compose.yaml` and the real Ollama run were NOT executed in CI: only `bench.py` is tested.

```bash
python -m unittest -v                    # no model, no key
docker compose up -d
docker compose exec ollama ollama pull llama3.2:1b
python bench.py http://127.0.0.1:11434 llama3.2:1b
```
