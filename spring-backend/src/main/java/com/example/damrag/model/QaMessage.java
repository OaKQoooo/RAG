package com.example.damrag.model;

import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "qa_message")
public class QaMessage {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "conversation_id")
    private Long conversationId;

    @Column(length = 20)
    private String role;

    @Lob
    private String content;

    @Lob
    @Column(name = "reference_json")
    private String referenceJson;

    @Column(name = "seq_no")
    private Integer seqNo;

    @Column(length = 30)
    private String status = "SUCCESS";

    @Column(name = "error_message", length = 1000)
    private String errorMessage;

    @Column(name = "created_at")
    private LocalDateTime createdAt;

    @PrePersist
    public void prePersist() {
        createdAt = LocalDateTime.now();
    }

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public Long getConversationId() { return conversationId; }
    public void setConversationId(Long conversationId) { this.conversationId = conversationId; }
    public String getRole() { return role; }
    public void setRole(String role) { this.role = role; }
    public String getContent() { return content; }
    public void setContent(String content) { this.content = content; }
    public String getReferenceJson() { return referenceJson; }
    public void setReferenceJson(String referenceJson) { this.referenceJson = referenceJson; }
    public Integer getSeqNo() { return seqNo; }
    public void setSeqNo(Integer seqNo) { this.seqNo = seqNo; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getErrorMessage() { return errorMessage; }
    public void setErrorMessage(String errorMessage) { this.errorMessage = errorMessage; }
    public LocalDateTime getCreatedAt() { return createdAt; }
}
