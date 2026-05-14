package com.example.damrag.controller;

import com.example.damrag.dto.ChatDtos.ChatRequest;
import com.example.damrag.dto.ChatDtos.ChatResponse;
import com.example.damrag.model.QaConversation;
import com.example.damrag.model.QaMessage;
import com.example.damrag.repository.QaConversationRepository;
import com.example.damrag.repository.QaMessageRepository;
import com.example.damrag.service.RagClient;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api")
public class ConversationController {
    private final QaConversationRepository conversationRepository;
    private final QaMessageRepository messageRepository;
    private final RagClient ragClient;
    private final ObjectMapper objectMapper;

    public ConversationController(
            QaConversationRepository conversationRepository,
            QaMessageRepository messageRepository,
            RagClient ragClient,
            ObjectMapper objectMapper
    ) {
        this.conversationRepository = conversationRepository;
        this.messageRepository = messageRepository;
        this.ragClient = ragClient;
        this.objectMapper = objectMapper;
    }

    @GetMapping("/conversations")
    public List<QaConversation> conversations(@RequestParam Long userId) {
        return conversationRepository.findByUserIdOrderByUpdatedAtDesc(userId);
    }

    @PostMapping("/conversations")
    public QaConversation createConversation(@RequestParam Long userId, @RequestParam(defaultValue = "新会话") String title) {
        QaConversation conversation = new QaConversation();
        conversation.setUserId(userId);
        conversation.setTitle(title);
        return conversationRepository.save(conversation);
    }

    @GetMapping("/conversations/{id}/messages")
    public List<QaMessage> messages(@PathVariable Long id) {
        return messageRepository.findByConversationIdOrderByCreatedAtAsc(id);
    }

    @PostMapping("/chat")
    public ChatResponse chat(@RequestBody ChatRequest request) {
        if (request.question() == null || request.question().isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "问题不能为空");
        }

        QaConversation conversation = resolveConversation(request);
        saveMessage(conversation.getId(), "user", request.question(), null);

        ChatResponse response = ragClient.ask(conversation.getId(), request);
        saveMessage(conversation.getId(), "assistant", response.answer(), toJson(response.references()));

        conversation.setTitle(titleFor(conversation.getTitle(), request.question()));
        conversationRepository.save(conversation);
        return response;
    }

    private QaConversation resolveConversation(ChatRequest request) {
        if (request.conversationId() != null) {
            return conversationRepository.findById(request.conversationId())
                    .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "会话不存在"));
        }
        QaConversation conversation = new QaConversation();
        conversation.setUserId(request.userId() == null ? 1L : request.userId());
        conversation.setTitle(titleFor(null, request.question()));
        return conversationRepository.save(conversation);
    }

    private void saveMessage(Long conversationId, String role, String content, String referenceJson) {
        QaMessage message = new QaMessage();
        message.setConversationId(conversationId);
        message.setRole(role);
        message.setContent(content);
        message.setReferenceJson(referenceJson);
        messageRepository.save(message);
    }

    private String toJson(Object value) {
        try {
            return objectMapper.writeValueAsString(value);
        } catch (JsonProcessingException e) {
            return "[]";
        }
    }

    private String titleFor(String currentTitle, String question) {
        if (currentTitle != null && !currentTitle.isBlank() && !"新会话".equals(currentTitle)) {
            return currentTitle;
        }
        return question.length() > 24 ? question.substring(0, 24) : question;
    }
}
