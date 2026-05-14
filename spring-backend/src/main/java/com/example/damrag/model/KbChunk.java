package com.example.damrag.model;

import jakarta.persistence.*;

@Entity
@Table(name = "kb_chunk")
public class KbChunk {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "clause_db_id")
    private Long clauseDbId;

    @Column(name = "document_id")
    private Long documentId;

    @Column(name = "chunk_index")
    private Integer chunkIndex;

    @Lob
    @Column(name = "chunk_text")
    private String chunkText;

    private Integer page;

    @Lob
    @Column(name = "bbox_json")
    private String bboxJson;

    @Column(name = "source_file")
    private String sourceFile;

    private String chapter;

    @Column(name = "milvus_id", length = 100)
    private String milvusId;

    @Column(name = "milvus_collection", length = 100)
    private String milvusCollection;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public Long getClauseDbId() { return clauseDbId; }
    public void setClauseDbId(Long clauseDbId) { this.clauseDbId = clauseDbId; }
    public Long getDocumentId() { return documentId; }
    public void setDocumentId(Long documentId) { this.documentId = documentId; }
    public Integer getChunkIndex() { return chunkIndex; }
    public void setChunkIndex(Integer chunkIndex) { this.chunkIndex = chunkIndex; }
    public String getChunkText() { return chunkText; }
    public void setChunkText(String chunkText) { this.chunkText = chunkText; }
    public Integer getPage() { return page; }
    public void setPage(Integer page) { this.page = page; }
    public String getBboxJson() { return bboxJson; }
    public void setBboxJson(String bboxJson) { this.bboxJson = bboxJson; }
    public String getSourceFile() { return sourceFile; }
    public void setSourceFile(String sourceFile) { this.sourceFile = sourceFile; }
    public String getChapter() { return chapter; }
    public void setChapter(String chapter) { this.chapter = chapter; }
    public String getMilvusId() { return milvusId; }
    public void setMilvusId(String milvusId) { this.milvusId = milvusId; }
    public String getMilvusCollection() { return milvusCollection; }
    public void setMilvusCollection(String milvusCollection) { this.milvusCollection = milvusCollection; }
}
