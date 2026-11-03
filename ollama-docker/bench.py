"""Measure an Ollama server: load time, prompt speed, generation speed. Standard library only."""
import json
import sys
import urllib.request

NS = 1_000_000_000


def post(base_url: str, path: str, body: dict, timeout: float = 600) -> dict:
    req = urllib.request.Request(
        base_url + path, data=json.dumps(body).encode(),
        headers={"content-type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.load(res)


def preload(base_url: str, model: str, keep_alive: str = "30m") -> dict:
    """An empty request loads the model into memory without generating anything."""
    return post(base_url, "/api/generate", {"model": model, "keep_alive": keep_alive})


def generate(base_url: str, model: str, prompt: str, num_predict: int = 64) -> dict:
    return post(base_url, "/api/generate", {
        "model": model, "prompt": prompt, "stream": False,
        "options": {"num_predict": num_predict}})


def summarize(r: dict) -> dict:
    """Turn the final response fields (all durations in nanoseconds) into readable numbers."""
    def rate(count_key: str, dur_key: str) -> float | None:
        count, dur = r.get(count_key, 0), r.get(dur_key, 0)
        return round(count / dur * NS, 2) if dur else None

    return {
        "load_s": round(r.get("load_duration", 0) / NS, 2),
        "total_s": round(r.get("total_duration", 0) / NS, 2),
        "prompt_tokens": r.get("prompt_eval_count", 0),
        "prompt_tokens_per_s": rate("prompt_eval_count", "prompt_eval_duration"),
        "output_tokens": r.get("eval_count", 0),
        "output_tokens_per_s": rate("eval_count", "eval_duration"),
    }


def main(base_url: str, model: str) -> None:
    prompt = "Explain in three sentences what a reverse proxy does."
    cold = summarize(generate(base_url, model, prompt))   # may include the model load
    warm = summarize(generate(base_url, model, prompt))   # model already in memory
    print(json.dumps({"cold": cold, "warm": warm}, indent=2))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:11434",
         sys.argv[2] if len(sys.argv) > 2 else "llama3.2:1b")
