package com.example.damrag.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.LocalDateTime;
import java.util.List;

public class ChatDtos {
    public record ChatTurn(String role, String content) {}
    public record ChatRequest(
            Long userId,
            Long conversationId,
            String question,
            List<ChatTurn> history,
            Boolean enableEvidence,
            Boolean enableSuggestions,
            String knowledgeScope,
            List<Long> documentIds,
            Integer topK
    ) {}
    public record ReferenceItem(String sourceFile, String clauseId, String chapter, Integer page, String bboxJson, String imageUrl, String contentPreview, Long documentId) {}
    public record ChatResponse(Long conversationId, String answer, List<ReferenceItem> references, List<String> suggestions) {}
    public record ConversationView(Long id, Long userId, String title, LocalDateTime createdAt, LocalDateTime updatedAt) {}
    public record CreateConversationRequest(Long userId, String title) {}
    public record DeleteConversationsRequest(Long userId, List<Long> conversationIds) {}
    public record MessageReferenceView(
            Long id,
            Long messageId,
            Long documentId,
            String sourceFile,
            String standardName,
            String clauseId,
            String chapter,
            Integer page,
            String bboxJson,
            String imageUrl,
            String contentPreview,
            Double score,
            Integer rank
    ) {}
    public record MessageView(
            Long id,
            Long conversationId,
            String role,
            String content,
            String referenceJson,
            Integer seqNo,
            String status,
            String errorMessage,
            LocalDateTime createdAt,
            List<MessageReferenceView> references
    ) {}
    public record RagChatRequest(
            String question,
            List<ChatTurn> history,
            @JsonProperty("top_k") Integer topK,
            @JsonProperty("enableEvidence") Boolean enableEvidence,
            @JsonProperty("enableSuggestions") Boolean enableSuggestions,
            @JsonProperty("userId") Long userId,
            @JsonProperty("knowledgeScope") String knowledgeScope,
            @JsonProperty("documentIds") List<Long> documentIds,
            @JsonProperty("restrictDocuments") Boolean restrictDocuments
    ) {}
    public record RagReferenceItem(String source_file, String clause_id, String chapter, Integer page, String bbox_json, String image_url, String content_preview, String document_id) {}
    public record RagChatResponse(String answer, List<RagReferenceItem> references, List<String> suggestions) {}
}
