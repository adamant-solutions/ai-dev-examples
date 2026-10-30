package com.example.aichat;

import java.util.List;

import org.springframework.ai.chat.client.ChatClient;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Flux;

@RestController
public class ChatController {

    private final ChatClient chatClient;

    // Spring Boot auto-configures a ChatClient.Builder for the model starter on the classpath.
    public ChatController(ChatClient.Builder builder) {
        this.chatClient = builder
                .defaultSystem("You are a concise assistant for Java developers. Answer in plain text.")
                .build();
    }

    // 1. Simple call: the whole answer as a String.
    @GetMapping("/ask")
    public String ask(@RequestParam String q) {
        return chatClient.prompt()
                .user(q)
                .call()
                .content();
    }

    // 2. Streaming: tokens are sent to the browser as they arrive (Server-Sent Events).
    @GetMapping(value = "/ask/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<String> askStream(@RequestParam String q) {
        return chatClient.prompt()
                .user(q)
                .stream()
                .content();
    }

    // 3. Structured output: the model's answer is mapped onto a Java record.
    public record LibraryAdvice(String library, String reason, List<String> alternatives) {}

    @GetMapping("/advice")
    public LibraryAdvice advice(@RequestParam String task) {
        return chatClient.prompt()
                .user(u -> u.text("Suggest one Java library for this task: {task}").param("task", task))
                .call()
                .entity(LibraryAdvice.class);
    }
}
