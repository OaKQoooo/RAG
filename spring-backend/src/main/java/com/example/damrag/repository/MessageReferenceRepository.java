package com.example.damrag.repository;

import com.example.damrag.model.MessageReference;
import java.util.Collection;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;

public interface MessageReferenceRepository extends JpaRepository<MessageReference, Long> {
    List<MessageReference> findByMessageIdOrderByRankAsc(Long messageId);
    List<MessageReference> findByMessageIdInOrderByMessageIdAscRankAsc(Collection<Long> messageIds);
    void deleteByMessageIdIn(Collection<Long> messageIds);
}
