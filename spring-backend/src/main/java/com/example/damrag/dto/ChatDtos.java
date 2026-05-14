package com.example.damrag.dto;

import java.util.List;

public class ChatDtos {
    public record ChatTurn(String role, String content) {}
    public record ChatRequest(Long userId, Long conversationId, String question, List<ChatTurn> history, Boolean enableEvidence) {}
    public record ReferenceItem(String sourceFile, String clauseId, String chapter, Integer page, String bboxJson, String imageUrl, String contentPreview) {}
    public record ChatResponse(Long conversationId, String answer, List<ReferenceItem> references, List<String> suggestions) {}
    public record RagChatRequest(String question, List<ChatTurn> history, Integer topK, Boolean enableEvidence) {}
    public record RagReferenceItem(String source_file, String clause_id, String chapter, Integer page, String bbox_json, String image_url, String content_preview) {}
    public record RagChatResponse(String answer, List<RagReferenceItem> references, List<String> suggestions) {}
}
