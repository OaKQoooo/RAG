package com.example.damrag.controller;

import com.example.damrag.service.AuthService;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/rag")
public class RagProxyController {
    private final AuthService authService;
    private final String serviceUrl;
    private final HttpClient httpClient;

    public RagProxyController(AuthService authService, @Value("${rag.service-url}") String serviceUrl) {
        this.authService = authService;
        this.serviceUrl = serviceUrl;
        this.httpClient = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .build();
    }

    @GetMapping("/snapshots/{fileName:.+}")
    public ResponseEntity<byte[]> snapshot(@PathVariable String fileName) {
        if (!fileName.matches("[a-f0-9]{40}\\.png")) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Invalid snapshot file name");
        }
        return forward(HttpRequest.newBuilder(URI.create(serviceUrl + "/snapshots/" + fileName))
                .GET()
                .build());
    }

    @GetMapping("/health")
    public ResponseEntity<byte[]> health(@RequestHeader(value = "Authorization", required = false) String token) {
        authService.requireAdmin(token);
        return forward(HttpRequest.newBuilder(URI.create(serviceUrl + "/health"))
                .header(HttpHeaders.ACCEPT, MediaType.APPLICATION_JSON_VALUE)
                .GET()
                .build());
    }

    @GetMapping("/quality")
    public ResponseEntity<byte[]> quality(@RequestHeader(value = "Authorization", required = false) String token) {
        authService.requireAdmin(token);
        return forward(HttpRequest.newBuilder(URI.create(serviceUrl + "/api/rag/quality"))
                .header(HttpHeaders.ACCEPT, MediaType.APPLICATION_JSON_VALUE)
                .GET()
                .build());
    }

    @PostMapping(value = "/debug/search", consumes = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<byte[]> debugSearch(
            @RequestHeader(value = "Authorization", required = false) String token,
            @RequestBody String body
    ) {
        authService.requireAdmin(token);
        return forward(HttpRequest.newBuilder(URI.create(serviceUrl + "/api/rag/debug/search"))
                .header(HttpHeaders.ACCEPT, MediaType.APPLICATION_JSON_VALUE)
                .header(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                .POST(HttpRequest.BodyPublishers.ofString(body, StandardCharsets.UTF_8))
                .build());
    }

    private ResponseEntity<byte[]> forward(HttpRequest request) {
        try {
            HttpResponse<byte[]> response = httpClient.send(request, HttpResponse.BodyHandlers.ofByteArray());
            ResponseEntity.BodyBuilder builder = ResponseEntity.status(response.statusCode());
            response.headers().firstValue(HttpHeaders.CONTENT_TYPE)
                    .ifPresent(value -> builder.header(HttpHeaders.CONTENT_TYPE, value));
            return builder.body(response.body());
        } catch (IOException ex) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "RAG service is unavailable", ex);
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "RAG request was interrupted", ex);
        }
    }
}
