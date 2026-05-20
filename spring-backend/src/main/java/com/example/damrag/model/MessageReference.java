package com.example.damrag.model;

import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "qa_message_reference")
public class MessageReference {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "message_id", nullable = false)
    private Long messageId;

    @Column(name = "document_id")
    private Long documentId;

    @Column(name = "source_file")
    private String sourceFile;

    @Column(name = "standard_name")
    private String standardName;

    @Column(name = "clause_id", length = 100)
    private String clauseId;

    private String chapter;

    private Integer page;

    @Lob
    @Column(name = "bbox_json")
    private String bboxJson;

    @Column(name = "image_url", length = 1000)
    private String imageUrl;

    @Lob
    @Column(name = "content_preview")
    private String contentPreview;

    private Double score;

    @Column(name = "rank_no")
    private Integer rank;

    @Column(name = "created_at")
    private LocalDateTime createdAt;

    @PrePersist
    public void prePersist() {
        createdAt = LocalDateTime.now();
    }

    public Long getId() { return id; }
    public Long getMessageId() { return messageId; }
    public void setMessageId(Long messageId) { this.messageId = messageId; }
    public Long getDocumentId() { return documentId; }
    public void setDocumentId(Long documentId) { this.documentId = documentId; }
    public String getSourceFile() { return sourceFile; }
    public void setSourceFile(String sourceFile) { this.sourceFile = sourceFile; }
    public String getStandardName() { return standardName; }
    public void setStandardName(String standardName) { this.standardName = standardName; }
    public String getClauseId() { return clauseId; }
    public void setClauseId(String clauseId) { this.clauseId = clauseId; }
    public String getChapter() { return chapter; }
    public void setChapter(String chapter) { this.chapter = chapter; }
    public Integer getPage() { return page; }
    public void setPage(Integer page) { this.page = page; }
    public String getBboxJson() { return bboxJson; }
    public void setBboxJson(String bboxJson) { this.bboxJson = bboxJson; }
    public String getImageUrl() { return imageUrl; }
    public void setImageUrl(String imageUrl) { this.imageUrl = imageUrl; }
    public String getContentPreview() { return contentPreview; }
    public void setContentPreview(String contentPreview) { this.contentPreview = contentPreview; }
    public Double getScore() { return score; }
    public void setScore(Double score) { this.score = score; }
    public Integer getRank() { return rank; }
    public void setRank(Integer rank) { this.rank = rank; }
    public LocalDateTime getCreatedAt() { return createdAt; }
}
