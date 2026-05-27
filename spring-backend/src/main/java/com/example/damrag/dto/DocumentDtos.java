package com.example.damrag.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;
import java.util.Map;

public class DocumentDtos {
    public record IngestResponse(
            @JsonProperty("file_name") String fileName,
            @JsonProperty("document_id") String documentId,
            Integer chunks,
            String status,
            @JsonProperty("quality_report") Map<String, Object> qualityReport
    ) {}

    public record RebuildDocument(
            @JsonProperty("document_id") String documentId,
            @JsonProperty("uploaded_by") String uploadedBy,
            @JsonProperty("file_path") String filePath
    ) {}

    public record RebuildRequest(List<RebuildDocument> documents) {}

    public record StatusRequest(Integer status) {}
}
