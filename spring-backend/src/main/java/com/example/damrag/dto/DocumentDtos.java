package com.example.damrag.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

public class DocumentDtos {
    public record IngestResponse(
            @JsonProperty("file_name") String fileName,
            @JsonProperty("document_id") String documentId,
            Integer chunks,
            String status
    ) {}

    public record RebuildDocument(
            @JsonProperty("document_id") String documentId,
            @JsonProperty("uploaded_by") String uploadedBy,
            @JsonProperty("file_path") String filePath
    ) {}

    public record RebuildRequest(List<RebuildDocument> documents) {}

    public record StatusRequest(Integer status) {}
}