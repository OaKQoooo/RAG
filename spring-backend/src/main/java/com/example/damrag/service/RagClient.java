package com.example.damrag.service;

import com.example.damrag.dto.ChatDtos.ChatRequest;
import com.example.damrag.dto.ChatDtos.ChatResponse;
import com.example.damrag.dto.ChatDtos.RagChatRequest;
import com.example.damrag.dto.ChatDtos.RagChatResponse;
import com.example.damrag.dto.ChatDtos.ReferenceItem;
import com.example.damrag.dto.ChatDtos.ChatTurn;
import com.example.damrag.dto.DocumentDtos.IngestResponse;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Path;
import java.nio.charset.StandardCharsets;
import java.util.List;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.FileSystemResource;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestClient;

@Service
public class RagClient implements RagGateway {
    private final RestClient restClient;
    private final String serviceUrl;
    private final ObjectMapper objectMapper;
    private final HttpClient httpClient;

    public RagClient(
            RestClient.Builder builder,
            @Value("${rag.service-url}") String serviceUrl,
            ObjectMapper objectMapper
    ) {
        this.serviceUrl = serviceUrl;
        this.objectMapper = objectMapper;
        this.httpClient = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .build();
        this.restClient = builder.baseUrl(serviceUrl).build();
    }

    @Override
    public ChatResponse ask(
            Long conversationId,
            Long userId,
            ChatRequest request,
            List<ChatTurn> history,
            List<Long> documentIds,
            boolean restrictDocuments
    ) {
        var ragRequest = new RagChatRequest(
                request.question(),
                history == null ? List.of() : history,
                request.topK() == null ? 5 : request.topK(),
                request.enableEvidence(),
                request.enableSuggestions(),
                userId,
                request.knowledgeScope(),
                documentIds == null ? List.of() : documentIds,
                restrictDocuments
        );
        RagChatResponse ragResponse = postChat(ragRequest);

        if (ragResponse == null) {
            throw new IllegalStateException("RAG 服务没有返回结果");
        }

        List<ReferenceItem> references = (ragResponse.references() == null ? List.<com.example.damrag.dto.ChatDtos.RagReferenceItem>of() : ragResponse.references())
                .stream()
                .map(ref -> new ReferenceItem(
                        ref.source_file(),
                        ref.clause_id(),
                        ref.chapter(),
                        ref.page(),
                        ref.bbox_json(),
                        absoluteSnapshotUrl(ref.image_url()),
                        ref.content_preview(),
                        parseLong(ref.document_id())
                ))
                .toList();

        List<String> suggestions = Boolean.FALSE.equals(request.enableSuggestions())
                ? List.of()
                : (ragResponse.suggestions() == null ? List.of() : ragResponse.suggestions());
        return new ChatResponse(conversationId, ragResponse.answer(), references, suggestions);
    }

    public IngestResponse ingest(Path filePath, Long documentId, Long uploadedBy, boolean append) {
        MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
        body.add("file", new FileSystemResource(filePath));
        body.add("document_id", String.valueOf(documentId));
        body.add("uploaded_by", String.valueOf(uploadedBy));
        body.add("append", String.valueOf(append));

        IngestResponse response = restClient.post()
                .uri("/api/rag/documents/ingest")
                .contentType(MediaType.MULTIPART_FORM_DATA)
                .body(body)
                .retrieve()
                .body(IngestResponse.class);

        if (response == null) {
            throw new IllegalStateException("RAG 入库服务没有返回结果");
        }
        return response;
    }

    private String absoluteSnapshotUrl(String value) {
        if (value == null || value.isBlank()) {
            return value;
        }
        if (value.startsWith("http://") || value.startsWith("https://")) {
            return value;
        }
        return serviceUrl + value;
    }

    private Long parseLong(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        try {
            return Long.valueOf(value);
        } catch (NumberFormatException ex) {
            return null;
        }
    }

    private String toJson(Object value) {
        try {
            return objectMapper.writeValueAsString(value);
        } catch (JsonProcessingException ex) {
            throw new IllegalStateException("RAG 请求序列化失败", ex);
        }
    }

    private RagChatResponse postChat(RagChatRequest ragRequest) {
        String payload = toJson(ragRequest);
        HttpRequest httpRequest = HttpRequest.newBuilder(URI.create(serviceUrl + "/api/rag/chat"))
                .version(HttpClient.Version.HTTP_1_1)
                .header("Content-Type", MediaType.APPLICATION_JSON_VALUE)
                .header("Accept", MediaType.APPLICATION_JSON_VALUE)
                .POST(HttpRequest.BodyPublishers.ofString(payload, StandardCharsets.UTF_8))
                .build();
        try {
            HttpResponse<String> response = httpClient.send(httpRequest, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                throw new IllegalStateException("RAG HTTP " + response.statusCode() + ": " + response.body());
            }
            return objectMapper.readValue(response.body(), RagChatResponse.class);
        } catch (IOException ex) {
            throw new IllegalStateException("RAG 服务请求失败：" + ex.getMessage(), ex);
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("RAG 服务请求被中断", ex);
        }
    }
}
