package com.example.damrag.repository;

import com.example.damrag.model.KbChunk;
import org.springframework.data.jpa.repository.JpaRepository;

public interface KbChunkRepository extends JpaRepository<KbChunk, Long> {
    long countByDocumentId(Long documentId);
}
