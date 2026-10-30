import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.time.Instant;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.Optional;
import java.util.Set;
import java.util.concurrent.ThreadLocalRandom;

/** Call an HTTP API and retry on 429/5xx, honouring Retry-After. Java 11+, no dependencies. */
public class RetryClient {

    private static final Set<Integer> RETRYABLE = Set.of(429, 500, 502, 503, 504);
    private final HttpClient http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(10)).build();

    static Optional<Duration> retryAfter(String value) {
        if (value == null || value.isBlank()) return Optional.empty();
        String v = value.trim();
        if (v.chars().allMatch(Character::isDigit)) return Optional.of(Duration.ofSeconds(Long.parseLong(v)));
        try {
            Instant when = ZonedDateTime.parse(v, DateTimeFormatter.RFC_1123_DATE_TIME).toInstant();
            Duration d = Duration.between(Instant.now(), when);
            return Optional.of(d.isNegative() ? Duration.ZERO : d);
        } catch (DateTimeParseException e) {
            return Optional.empty();
        }
    }

    public String postJson(String url, String json, int maxAttempts) throws IOException, InterruptedException {
        long baseMs = 500, capMs = 30_000;
        for (int attempt = 1; ; attempt++) {
            HttpRequest req = HttpRequest.newBuilder(URI.create(url))
                    .timeout(Duration.ofSeconds(60))
                    .header("content-type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(json))
                    .build();
            HttpResponse<String> res = http.send(req, HttpResponse.BodyHandlers.ofString());
            if (res.statusCode() < 300) return res.body();
            if (!RETRYABLE.contains(res.statusCode()) || attempt == maxAttempts) {
                throw new IOException("HTTP " + res.statusCode() + ": " + res.body());
            }
            long ceiling = Math.min(capMs, baseMs << attempt);
            long waitMs = retryAfter(res.headers().firstValue("retry-after").orElse(null))
                    .map(Duration::toMillis)
                    .orElseGet(() -> ThreadLocalRandom.current().nextLong(ceiling + 1)); // full jitter
            waitMs = Math.min(waitMs, capMs);
            System.out.printf("HTTP %d, attempt %d/%d, waiting %.1fs%n", res.statusCode(), attempt, maxAttempts, waitMs / 1000.0);
            Thread.sleep(waitMs);
        }
    }

    public static void main(String[] args) throws Exception {
        System.out.println(new RetryClient().postJson(args[0], "{\"prompt\":\"hello\"}", 5));
    }
}
