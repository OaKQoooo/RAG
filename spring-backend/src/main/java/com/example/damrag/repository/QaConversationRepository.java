package com.example.damrag.repository;

import com.example.damrag.model.QaConversation;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;

public interface QaConversationRepository extends JpaRepository<QaConversation, Long> {
    List<QaConversation> findByUserIdOrderByUpdatedAtDesc(Long userId);
    void deleteByUserId(Long userId);
}
