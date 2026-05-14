package com.example.damrag.model;

import jakarta.persistence.*;

@Entity
@Table(name = "kb_clause")
public class KbClause {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "document_id")
    private Long documentId;

    @Column(name = "chapter_title")
    private String chapterTitle;

    @Column(name = "clause_id", length = 100)
    private String clauseId;

    @Lob
    private String content;

    private Integer page;

    @Lob
    @Column(name = "bbox_json")
    private String bboxJson;

    @Column(name = "source_file")
    private String sourceFile;

    @Column(name = "node_type", length = 20)
    private String nodeType;

    @Column(name = "page_width")
    private Double pageWidth;

    @Column(name = "page_height")
    private Double pageHeight;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public Long getDocumentId() { return documentId; }
    public void setDocumentId(Long documentId) { this.documentId = documentId; }
    public String getChapterTitle() { return chapterTitle; }
    public void setChapterTitle(String chapterTitle) { this.chapterTitle = chapterTitle; }
    public String getClauseId() { return clauseId; }
    public void setClauseId(String clauseId) { this.clauseId = clauseId; }
    public String getContent() { return content; }
    public void setContent(String content) { this.content = content; }
    public Integer getPage() { return page; }
    public void setPage(Integer page) { this.page = page; }
    public String getBboxJson() { return bboxJson; }
    public void setBboxJson(String bboxJson) { this.bboxJson = bboxJson; }
    public String getSourceFile() { return sourceFile; }
    public void setSourceFile(String sourceFile) { this.sourceFile = sourceFile; }
    public String getNodeType() { return nodeType; }
    public void setNodeType(String nodeType) { this.nodeType = nodeType; }
    public Double getPageWidth() { return pageWidth; }
    public void setPageWidth(Double pageWidth) { this.pageWidth = pageWidth; }
    public Double getPageHeight() { return pageHeight; }
    public void setPageHeight(Double pageHeight) { this.pageHeight = pageHeight; }
}
