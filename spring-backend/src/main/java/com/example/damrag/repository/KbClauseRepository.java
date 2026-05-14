package com.example.damrag.repository;

import com.example.damrag.model.KbClause;
import org.springframework.data.jpa.repository.JpaRepository;

public interface KbClauseRepository extends JpaRepository<KbClause, Long> {
    long countByDocumentId(Long documentId);
}
