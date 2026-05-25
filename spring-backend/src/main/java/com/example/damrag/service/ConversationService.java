package com.example.damrag.service;

import com.example.damrag.dto.ChatDtos.ConversationView;
import com.example.damrag.dto.ProfileDtos.Result;
import com.example.damrag.model.QaConversation;
import com.example.damrag.model.QaMessage;
import com.example.damrag.repository.MessageReferenceRepository;
import com.example.damrag.repository.QaConversationRepository;
import com.example.damrag.repository.QaMessageRepository;
import jakarta.transaction.Transactional;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

@Service
public class ConversationService {
    private final QaConversationRepository conversationRepository;
    private final QaMessageRepository messageRepository;
    private final MessageReferenceRepository referenceRepository;

    public ConversationService(
            QaConversationRepository conversationRepository,
            QaMessageRepository messageRepository,
            MessageReferenceRepository referenceRepository
    ) {
        this.conversationRepository = conversationRepository;
        this.messageRepository = messageRepository;
        this.referenceRepository = referenceRepository;
    }

    public List<ConversationView> listConversations(Long userId) {
        return conversationRepository.findByUserIdOrderByUpdatedAtDesc(userId)
                .stream()
                .map(this::toView)
                .toList();
    }

    public ConversationView createConversation(Long userId, String title) {
        QaConversation conversation = new QaConversation();
        conversation.setUserId(userId);
        conversation.setTitle(normalizeTitle(title, "新会话"));
        return toView(conversationRepository.save(conversation));
    }

    public QaConversation resolveConversation(Long userId, Long conversationId, String question) {
        if (conversationId != null) {
            QaConversation conversation = conversationRepository.findById(conversationId)
                    .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "会话不存在"));
            ensureOwner(conversation, userId);
            return conversation;
        }

        QaConversation conversation = new QaConversation();
        conversation.setUserId(userId);
        conversation.setTitle(titleFor(null, question));
        return conversationRepository.save(conversation);
    }

    public void checkOwner(Long userId, Long conversationId) {
        QaConversation conversation = conversationRepository.findById(conversationId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "会话不存在"));
        ensureOwner(conversation, userId);
    }

    @Transactional
    public Result deleteConversations(Long userId, List<Long> conversationIds) {
        if (conversationIds == null || conversationIds.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "请选择要删除的会话");
        }

        List<Long> distinctIds = conversationIds.stream()
                .filter(id -> id != null)
                .distinct()
                .toList();
        if (distinctIds.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "请选择要删除的会话");
        }

        List<QaConversation> conversations = conversationRepository.findAllById(distinctIds);
        if (conversations.size() != distinctIds.size()) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "部分会话不存在");
        }
        conversations.forEach(conversation -> ensureOwner(conversation, userId));

        List<Long> messageIds = messageRepository.findByConversationIdIn(distinctIds)
                .stream()
                .map(QaMessage::getId)
                .toList();
        if (!messageIds.isEmpty()) {
            referenceRepository.deleteByMessageIdIn(messageIds);
        }
        messageRepository.deleteByConversationIdIn(distinctIds);
        conversationRepository.deleteAll(conversations);
        return new Result(true, "已删除选中的会话");
    }

    public QaConversation updateTitle(QaConversation conversation, String question) {
        conversation.setTitle(titleFor(conversation.getTitle(), question));
        return conversationRepository.save(conversation);
    }

    public ConversationView toView(QaConversation conversation) {
        return new ConversationView(
                conversation.getId(),
                conversation.getUserId(),
                conversation.getTitle(),
                conversation.getCreatedAt(),
                conversation.getUpdatedAt()
        );
    }

    private void ensureOwner(QaConversation conversation, Long userId) {
        if (!conversation.getUserId().equals(userId)) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "无权访问该会话");
        }
    }

    private String titleFor(String currentTitle, String question) {
        if (currentTitle != null && !currentTitle.isBlank() && !"新会话".equals(currentTitle)) {
            return currentTitle;
        }
        return normalizeTitle(question, "新会话");
    }

    private String normalizeTitle(String value, String fallback) {
        String title = value == null ? "" : value.trim();
        if (title.isBlank()) {
            title = fallback;
        }
        return title.length() > 24 ? title.substring(0, 24) : title;
    }
}
