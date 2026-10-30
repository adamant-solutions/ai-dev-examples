# Spring AI 2.0 + Ollama: chat, streaming and structured output

Article: https://tools.adamant-solutions.com/blog/spring-ai-ollama-chatclient/

Versions (checked 30 October 2026 on Maven Central): Spring Boot 4.1.2, Spring AI 2.0.2, Java 21.

```bash
# 1. Install Ollama (https://ollama.com) and start it
ollama pull llama3.2
# 2. Run the app
mvn spring-boot:run
# 3. Try it
curl "localhost:8080/ask?q=What%20is%20a%20Java%20record"
curl -N "localhost:8080/ask/stream?q=Name%20three%20Java%20build%20tools"
curl "localhost:8080/advice?task=parse%20CSV%20files"
```

Change the model in `src/main/resources/application.properties` (`spring.ai.ollama.chat.model`).
