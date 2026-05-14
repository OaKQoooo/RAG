package com.example.damrag.service;

import com.example.damrag.dto.ChatDtos.ChatRequest;
import com.example.damrag.dto.ChatDtos.ChatResponse;
import com.example.damrag.dto.ChatDtos.RagChatRequest;
import com.example.damrag.dto.ChatDtos.RagChatResponse;
import com.example.damrag.dto.ChatDtos.ReferenceItem;
import com.example.damrag.dto.DocumentDtos.IngestResponse;
import java.nio.file.Path;
import java.util.List;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.FileSystemResource;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestClient;

@Service
public class RagClient {
    private final RestClient restClient;
    private final String serviceUrl;

    public RagClient(RestClient.Builder builder, @Value("${rag.service-url}") String serviceUrl) {
        this.serviceUrl = serviceUrl;
        this.restClient = builder.baseUrl(serviceUrl).build();
    }

    public ChatResponse ask(Long conversationId, ChatRequest request) {
        var ragRequest = new RagChatRequest(
                request.question(),
                request.history() == null ? List.of() : request.history(),
                5,
                request.enableEvidence()
        );
        RagChatResponse ragResponse = restClient.post()
                .uri("/api/rag/chat")
                .contentType(MediaType.APPLICATION_JSON)
                .body(ragRequest)
                .retrieve()
                .body(RagChatResponse.class);

        if (ragResponse == null) {
            throw new IllegalStateException("RAG 服务没有返回结果");
        }

        List<ReferenceItem> references = ragResponse.references().stream()
                .map(ref -> new ReferenceItem(
                        ref.source_file(),
                        ref.clause_id(),
                        ref.chapter(),
                        ref.page(),
                        ref.bbox_json(),
                        absoluteSnapshotUrl(ref.image_url()),
                        ref.content_preview()
                ))
                .toList();

        return new ChatResponse(conversationId, ragResponse.answer(), references, ragResponse.suggestions());
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
}
