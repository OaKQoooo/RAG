package com.example.damrag.service;

import com.example.damrag.dto.ChatDtos.ChatTurn;
import com.example.damrag.dto.ChatDtos.MessageReferenceView;
import com.example.damrag.dto.ChatDtos.MessageView;
import com.example.damrag.dto.ChatDtos.ReferenceItem;
import com.example.damrag.model.MessageReference;
import com.example.damrag.model.QaMessage;
import com.example.damrag.repository.MessageReferenceRepository;
import com.example.damrag.repository.QaMessageRepository;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.Collection;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;
import org.springframework.stereotype.Service;

@Service
public class MessageService {
    private static final int HISTORY_LIMIT = 12;

    private final QaMessageRepository messageRepository;
    private final MessageReferenceRepository referenceRepository;
    private final ObjectMapper objectMapper;

    public MessageService(
            QaMessageRepository messageRepository,
            MessageReferenceRepository referenceRepository,
            ObjectMapper objectMapper
    ) {
        this.messageRepository = messageRepository;
        this.referenceRepository = referenceRepository;
        this.objectMapper = objectMapper;
    }

    public QaMessage saveUserMessage(Long conversationId, String content) {
        return saveMessage(conversationId, "user", content, null, "SUCCESS", null);
    }

    public QaMessage saveAssistantMessage(Long conversationId, String answer, List<ReferenceItem> references) {
        QaMessage message = saveMessage(conversationId, "assistant", answer, toJson(references), "SUCCESS", null);
        saveReferences(message.getId(), references);
        return message;
    }

    public QaMessage saveFailedAssistantMessage(Long conversationId, String errorMessage) {
        return saveMessage(conversationId, "assistant", "问答服务暂时不可用，请稍后重试。", "[]", "FAILED", errorMessage);
    }

    public List<MessageView> listMessages(Long conversationId) {
        List<QaMessage> messages = messageRepository.findByConversationIdOrderByCreatedAtAsc(conversationId);
        List<Long> messageIds = messages.stream().map(QaMessage::getId).toList();
        Map<Long, List<MessageReferenceView>> referencesByMessageId = messageIds.isEmpty()
                ? Map.of()
                : referenceRepository.findByMessageIdInOrderByMessageIdAscRankAsc(messageIds)
                        .stream()
                        .map(this::toReferenceView)
                        .collect(Collectors.groupingBy(MessageReferenceView::messageId));

        return messages.stream()
                .map(message -> toView(message, referencesByMessageId.getOrDefault(message.getId(), List.of())))
                .toList();
    }

    public List<ChatTurn> buildHistory(Long conversationId) {
        List<QaMessage> messages = messageRepository.findByConversationIdOrderByCreatedAtAsc(conversationId);
        int fromIndex = Math.max(0, messages.size() - HISTORY_LIMIT);
        return messages.subList(fromIndex, messages.size())
                .stream()
                .filter(message -> "SUCCESS".equalsIgnoreCase(message.getStatus()))
                .filter(message -> "user".equals(message.getRole()) || "assistant".equals(message.getRole()))
                .filter(message -> message.getContent() != null && !message.getContent().isBlank())
                .map(message -> new ChatTurn(message.getRole(), message.getContent()))
                .toList();
    }

    public void deleteReferencesByMessageIds(Collection<Long> messageIds) {
        if (messageIds != null && !messageIds.isEmpty()) {
            referenceRepository.deleteByMessageIdIn(messageIds);
        }
    }

    private QaMessage saveMessage(
            Long conversationId,
            String role,
            String content,
            String referenceJson,
            String status,
            String errorMessage
    ) {
        QaMessage message = new QaMessage();
        message.setConversationId(conversationId);
        message.setRole(role);
        message.setContent(content);
        message.setReferenceJson(referenceJson);
        message.setSeqNo((int) messageRepository.countByConversationId(conversationId) + 1);
        message.setStatus(status);
        message.setErrorMessage(errorMessage);
        return messageRepository.save(message);
    }

    private void saveReferences(Long messageId, List<ReferenceItem> references) {
        if (references == null || references.isEmpty()) {
            return;
        }

        int rank = 1;
        for (ReferenceItem item : references) {
            MessageReference reference = new MessageReference();
            reference.setMessageId(messageId);
            reference.setDocumentId(item.documentId());
            reference.setSourceFile(item.sourceFile());
            reference.setStandardName(item.sourceFile());
            reference.setClauseId(item.clauseId());
            reference.setChapter(item.chapter());
            reference.setPage(item.page());
            reference.setBboxJson(item.bboxJson());
            reference.setImageUrl(item.imageUrl());
            reference.setContentPreview(item.contentPreview());
            reference.setRank(rank++);
            referenceRepository.save(reference);
        }
    }

    private MessageView toView(QaMessage message, List<MessageReferenceView> references) {
        return new MessageView(
                message.getId(),
                message.getConversationId(),
                message.getRole(),
                message.getContent(),
                message.getReferenceJson(),
                message.getSeqNo(),
                message.getStatus(),
                message.getErrorMessage(),
                message.getCreatedAt(),
                references
        );
    }

    private MessageReferenceView toReferenceView(MessageReference reference) {
        return new MessageReferenceView(
                reference.getId(),
                reference.getMessageId(),
                reference.getDocumentId(),
                reference.getSourceFile(),
                reference.getStandardName(),
                reference.getClauseId(),
                reference.getChapter(),
                reference.getPage(),
                reference.getBboxJson(),
                reference.getImageUrl(),
                reference.getContentPreview(),
                reference.getScore(),
                reference.getRank()
        );
    }

    private String toJson(Object value) {
        try {
            return objectMapper.writeValueAsString(value == null ? List.of() : value);
        } catch (JsonProcessingException e) {
            return "[]";
        }
    }
}
