package com.example.damrag.repository;

import com.example.damrag.model.QaMessage;
import java.util.Collection;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;

public interface QaMessageRepository extends JpaRepository<QaMessage, Long> {
    List<QaMessage> findByConversationIdOrderByCreatedAtAsc(Long conversationId);
    List<QaMessage> findByConversationIdIn(Collection<Long> conversationIds);
    long countByConversationId(Long conversationId);
    void deleteByConversationIdIn(Collection<Long> conversationIds);
}
