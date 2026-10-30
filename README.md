# AI dev examples

Small, tested code examples for developers who integrate AI models into real applications.
Each folder belongs to an article on the [Adamant Tools blog](https://tools.adamant-solutions.com/blog/) and is checked automatically on every change (see `.github/workflows/test.yml`).

| Example | Stack | Article |
|---|---|---|
| [`spring-ai-chat`](spring-ai-chat/) | Java 21, Spring Boot 4.1, Spring AI 2.0, Ollama | [Calling an LLM from Spring Boot with Spring AI 2.0](https://tools.adamant-solutions.com/blog/spring-ai-ollama-chatclient/) |
| [`retry-429`](retry-429/) | Python, Node.js, Java (no dependencies) | [HTTP 429 from AI APIs: retry with backoff and Retry-After](https://tools.adamant-solutions.com/blog/retry-429-retry-after/) |
| [`stream-sse`](stream-sse/) | Python (FastAPI 0.162), browser JavaScript | [Stream an LLM answer to the browser with Server-Sent Events](https://tools.adamant-solutions.com/blog/stream-llm-sse-browser/) |
| [`token-costs`](token-costs/) | Python (tiktoken, anthropic, openai), JavaScript (js-tiktoken) | [Count tokens and estimate costs before calling a model](https://tools.adamant-solutions.com/blog/count-tokens-costs/) |

## Rules for every example
- Library versions are pinned and checked on the day the article is written.
- The code compiles and its tests pass in CI before the article is published.
- No API keys in the repository: examples run against a local model (Ollama) or a local test server.

Free browser tools for API work: [tools.adamant-solutions.com](https://tools.adamant-solutions.com/).

MIT licence. Made by [Adamant Solutions](https://adamant-solutions.com/).
