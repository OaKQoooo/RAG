package com.example.damrag.dto;

import java.time.LocalDateTime;

public class ActivityDtos {
    public record ActivityView(
            Long id,
            Long actorId,
            String actorName,
            String actorRole,
            String action,
            String message,
            String targetType,
            Long targetId,
            LocalDateTime createdAt
    ) {}
}
