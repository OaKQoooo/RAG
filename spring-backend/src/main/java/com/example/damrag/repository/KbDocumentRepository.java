package com.example.damrag.repository;

import com.example.damrag.model.KbDocument;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;

public interface KbDocumentRepository extends JpaRepository<KbDocument, Long> {
    List<KbDocument> findByUploadedByOrderByCreatedAtDesc(Long uploadedBy);
    List<KbDocument> findByVisibilityOrderByCreatedAtDesc(String visibility);
    List<KbDocument> findByVisibilityOrUploadedByOrderByCreatedAtDesc(String visibility, Long uploadedBy);
}
