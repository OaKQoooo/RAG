package com.example.damrag.service;

import com.example.damrag.dto.ChatDtos.ChatRequest;
import com.example.damrag.dto.ChatDtos.ChatResponse;
import com.example.damrag.dto.ChatDtos.ChatTurn;
import java.util.List;

public interface RagGateway {
    ChatResponse ask(
            Long conversationId,
            Long userId,
            ChatRequest request,
            List<ChatTurn> history,
            List<Long> documentIds,
            boolean restrictDocuments
    );
}
