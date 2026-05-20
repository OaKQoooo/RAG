package com.example.damrag.service;

import com.example.damrag.dto.ChatDtos.ConversationView;
import com.example.damrag.model.QaConversation;
import com.example.damrag.repository.QaConversationRepository;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

@Service
public class ConversationService {
    private final QaConversationRepository conversationRepository;

    public ConversationService(QaConversationRepository conversationRepository) {
        this.conversationRepository = conversationRepository;
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
