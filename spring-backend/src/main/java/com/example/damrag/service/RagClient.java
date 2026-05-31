package com.example.damrag.service;

import com.example.damrag.dto.ChatDtos.ChatRequest;
import com.example.damrag.dto.ChatDtos.ChatResponse;
import com.example.damrag.dto.ChatDtos.ChatTurn;
import com.example.damrag.dto.ChatDtos.RagChatRequest;
import com.example.damrag.dto.ChatDtos.RagChatResponse;
import com.example.damrag.dto.ChatDtos.ReferenceItem;
import com.example.damrag.dto.DocumentDtos.IngestResponse;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;
import com.example.damrag.dto.DocumentDtos.RebuildDocument;
import com.example.damrag.dto.DocumentDtos.RebuildRequest;
import com.example.damrag.model.KbDocument;

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
            throw new IllegalStateException("RAG service returned an empty response");
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
        try {
            String boundary = "DamRagBoundary-" + UUID.randomUUID();
            HttpRequest httpRequest = HttpRequest.newBuilder(URI.create(serviceUrl + "/api/rag/documents/ingest"))
                    .version(HttpClient.Version.HTTP_1_1)
                    .header("Content-Type", "multipart/form-data; boundary=" + boundary)
                    .header("Accept", MediaType.APPLICATION_JSON_VALUE)
                    .POST(multipartBody(filePath, documentId, uploadedBy, append, boundary))
                    .build();

            HttpResponse<String> response = httpClient.send(httpRequest, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                throw new IllegalStateException("RAG HTTP " + response.statusCode() + ": " + response.body());
            }

            IngestResponse ingestResponse = objectMapper.readValue(response.body(), IngestResponse.class);
            if (ingestResponse == null) {
                throw new IllegalStateException("RAG ingest service returned an empty response");
            }
            return ingestResponse;
        } catch (IOException ex) {
            throw new IllegalStateException("RAG ingest request failed: " + ex.getMessage(), ex);
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("RAG ingest request was interrupted", ex);
        }
    }

    public IngestResponse rebuild(List<KbDocument> documents, Path uploadDir) {
        List<RebuildDocument> payload = documents.stream()
                .filter(doc -> doc.getStoredName() != null && !doc.getStoredName().isBlank())
                .map(doc -> new RebuildDocument(
                        String.valueOf(doc.getId()),
                        doc.getUploadedBy() == null ? "" : String.valueOf(doc.getUploadedBy()),
                        uploadDir.resolve(doc.getStoredName()).toAbsolutePath().normalize().toString()
                ))
                .toList();

        String body = toJson(new RebuildRequest(payload));

        HttpRequest httpRequest = HttpRequest.newBuilder(URI.create(serviceUrl + "/api/rag/documents/rebuild"))
                .version(HttpClient.Version.HTTP_1_1)
                .header("Content-Type", MediaType.APPLICATION_JSON_VALUE)
                .header("Accept", MediaType.APPLICATION_JSON_VALUE)
                .POST(HttpRequest.BodyPublishers.ofString(body, StandardCharsets.UTF_8))
                .build();

        try {
            HttpResponse<String> response = httpClient.send(httpRequest, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                throw new IllegalStateException("RAG HTTP " + response.statusCode() + ": " + response.body());
            }
            return objectMapper.readValue(response.body(), IngestResponse.class);
        } catch (IOException ex) {
            throw new IllegalStateException("RAG rebuild request failed: " + ex.getMessage(), ex);
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("RAG rebuild request was interrupted", ex);
        }
    }

    public void deleteDocument(Long documentId) {
        HttpRequest httpRequest = HttpRequest.newBuilder(URI.create(serviceUrl + "/api/rag/documents/" + documentId))
                .version(HttpClient.Version.HTTP_1_1)
                .header("Accept", MediaType.APPLICATION_JSON_VALUE)
                .DELETE()
                .build();

        try {
            HttpResponse<String> response = httpClient.send(httpRequest, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                throw new IllegalStateException("RAG HTTP " + response.statusCode() + ": " + response.body());
            }
        } catch (IOException ex) {
            throw new IllegalStateException("RAG delete request failed: " + ex.getMessage(), ex);
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("RAG delete request was interrupted", ex);
        }
    }

    private HttpRequest.BodyPublisher multipartBody(
            Path filePath,
            Long documentId,
            Long uploadedBy,
            boolean append,
            String boundary
    ) throws IOException {
        List<byte[]> parts = new ArrayList<>();
        addFormField(parts, boundary, "document_id", documentId == null ? "" : String.valueOf(documentId));
        addFormField(parts, boundary, "uploaded_by", uploadedBy == null ? "" : String.valueOf(uploadedBy));
        addFormField(parts, boundary, "append", String.valueOf(append));
        addFileField(parts, boundary, "file", filePath);
        parts.add(("--" + boundary + "--\r\n").getBytes(StandardCharsets.UTF_8));
        return HttpRequest.BodyPublishers.ofByteArrays(parts);
    }

    private void addFormField(List<byte[]> parts, String boundary, String name, String value) {
        parts.add(("--" + boundary + "\r\n").getBytes(StandardCharsets.UTF_8));
        parts.add(("Content-Disposition: form-data; name=\"" + name + "\"\r\n\r\n").getBytes(StandardCharsets.UTF_8));
        parts.add((value + "\r\n").getBytes(StandardCharsets.UTF_8));
    }

    private void addFileField(List<byte[]> parts, String boundary, String name, Path filePath) throws IOException {
        String filename = filePath.getFileName().toString().replace("\"", "");
        parts.add(("--" + boundary + "\r\n").getBytes(StandardCharsets.UTF_8));
        parts.add(("Content-Disposition: form-data; name=\"" + name + "\"; filename=\"" + filename + "\"\r\n").getBytes(StandardCharsets.UTF_8));
        parts.add("Content-Type: application/pdf\r\n\r\n".getBytes(StandardCharsets.UTF_8));
        parts.add(Files.readAllBytes(filePath));
        parts.add("\r\n".getBytes(StandardCharsets.UTF_8));
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
            throw new IllegalStateException("RAG request serialization failed", ex);
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
            throw new IllegalStateException("RAG service request failed: " + ex.getMessage(), ex);
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("RAG service request was interrupted", ex);
        }
    }
}
