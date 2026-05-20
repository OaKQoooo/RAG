package com.example.damrag.service;

import com.example.damrag.dto.ChatDtos.ChatRequest;
import com.example.damrag.dto.ChatDtos.ChatResponse;
import com.example.damrag.dto.ChatDtos.ChatTurn;
import com.example.damrag.model.KbDocument;
import com.example.damrag.model.QaConversation;
import com.example.damrag.repository.KbDocumentRepository;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClientResponseException;
import org.springframework.web.server.ResponseStatusException;

@Service
public class ChatService {
    private final ConversationService conversationService;
    private final MessageService messageService;
    private final RagGateway ragGateway;
    private final KbDocumentRepository documentRepository;

    public ChatService(
            ConversationService conversationService,
            MessageService messageService,
            RagGateway ragGateway,
            KbDocumentRepository documentRepository
    ) {
        this.conversationService = conversationService;
        this.messageService = messageService;
        this.ragGateway = ragGateway;
        this.documentRepository = documentRepository;
    }

    public ChatResponse ask(Long userId, ChatRequest request) {
        validateRequest(userId, request);
        QaConversation conversation = conversationService.resolveConversation(userId, request.conversationId(), request.question());
        List<ChatTurn> history = messageService.buildHistory(conversation.getId());
        DocumentScope documentScope = resolveDocumentScope(userId, request);

        messageService.saveUserMessage(conversation.getId(), request.question());
        try {
            ChatResponse response = ragGateway.ask(
                    conversation.getId(),
                    userId,
                    request,
                    history,
                    documentScope.documentIds(),
                    documentScope.restrictDocuments()
            );
            messageService.saveAssistantMessage(conversation.getId(), response.answer(), response.references());
            conversationService.updateTitle(conversation, request.question());
            return response;
        } catch (RuntimeException ex) {
            String message = ragErrorMessage(ex);
            messageService.saveFailedAssistantMessage(conversation.getId(), message);
            conversationService.updateTitle(conversation, request.question());
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "RAG 服务调用失败：" + message, ex);
        }
    }

    private void validateRequest(Long userId, ChatRequest request) {
        if (userId == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "请先登录");
        }
        if (request == null || request.question() == null || request.question().isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "问题不能为空");
        }
    }

    private DocumentScope resolveDocumentScope(Long userId, ChatRequest request) {
        List<Long> explicitDocumentIds = request.documentIds() == null ? List.of() : request.documentIds();
        if (!explicitDocumentIds.isEmpty()) {
            return new DocumentScope(validateExplicitDocuments(userId, explicitDocumentIds), true);
        }

        String scope = request.knowledgeScope() == null ? "ALL" : request.knowledgeScope().trim().toUpperCase();
        long knownDocumentCount = documentRepository.count();
        if ("SYSTEM".equals(scope)) {
            return new DocumentScope(documentIds(documentRepository.findByVisibilityOrderByCreatedAtDesc("public")), true);
        }
        if ("PERSONAL".equals(scope)) {
            return new DocumentScope(documentIds(documentRepository.findByUploadedByOrderByCreatedAtDesc(userId)), true);
        }
        if (!"ALL".equals(scope)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "知识库范围参数无效");
        }
        if (knownDocumentCount == 0) {
            return new DocumentScope(List.of(), false);
        }
        return new DocumentScope(documentIds(documentRepository.findByVisibilityOrUploadedByOrderByCreatedAtDesc("public", userId)), true);
    }

    private List<Long> validateExplicitDocuments(Long userId, List<Long> documentIds) {
        Set<Long> requestedIds = new HashSet<>(documentIds);
        List<KbDocument> documents = documentRepository.findAllById(requestedIds);
        Set<Long> foundIds = documents.stream().map(KbDocument::getId).collect(java.util.stream.Collectors.toSet());
        if (!foundIds.containsAll(requestedIds)) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "部分文档不存在");
        }

        boolean hasForbidden = documents.stream()
                .anyMatch(document -> !"public".equals(document.getVisibility()) && !userId.equals(document.getUploadedBy()));
        if (hasForbidden) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "无权检索所选文档");
        }
        return documentIds.stream().distinct().toList();
    }

    private List<Long> documentIds(List<KbDocument> documents) {
        return documents.stream()
                .map(KbDocument::getId)
                .distinct()
                .toList();
    }

    private String ragErrorMessage(RuntimeException ex) {
        if (ex instanceof RestClientResponseException responseException) {
            String body = responseException.getResponseBodyAsString();
            if (body != null && !body.isBlank()) {
                return body;
            }
        }
        return ex.getMessage();
    }

    private record DocumentScope(List<Long> documentIds, boolean restrictDocuments) {}
}
