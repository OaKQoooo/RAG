package com.example.damrag.dto;

public class DocumentDtos {
    public record IngestResponse(String fileName, String documentId, Integer chunks, String status) {}
    public record StatusRequest(Integer status) {}
}
