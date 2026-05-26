package com.example.damrag.controller;

import com.example.damrag.dto.ChatDtos.ChatRequest;
import com.example.damrag.dto.ChatDtos.ChatResponse;
import com.example.damrag.dto.ChatDtos.ConversationView;
import com.example.damrag.dto.ChatDtos.CreateConversationRequest;
import com.example.damrag.dto.ChatDtos.DeleteConversationsRequest;
import com.example.damrag.dto.ChatDtos.MessageView;
import com.example.damrag.dto.ProfileDtos.Result;
import com.example.damrag.model.User;
import com.example.damrag.service.AuthService;
import com.example.damrag.service.ChatService;
import com.example.damrag.service.ConversationService;
import com.example.damrag.service.MessageService;
import java.util.List;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api")
public class ConversationController {
    private final ChatService chatService;
    private final ConversationService conversationService;
    private final MessageService messageService;
    private final AuthService authService;

    public ConversationController(
            ChatService chatService,
            ConversationService conversationService,
            MessageService messageService,
            AuthService authService
    ) {
        this.chatService = chatService;
        this.conversationService = conversationService;
        this.messageService = messageService;
        this.authService = authService;
    }

    @GetMapping("/conversations")
    public List<ConversationView> conversations(
            @RequestHeader(value = "Authorization", required = false) String token
    ) {
        return conversationService.listConversations(currentUserId(token));
    }

    @PostMapping("/conversations")
    public ConversationView createConversation(
            @RequestHeader(value = "Authorization", required = false) String token,
            @RequestParam(required = false) String title,
            @RequestBody(required = false) CreateConversationRequest request
    ) {
        String resolvedTitle = request != null && request.title() != null ? request.title() : title;
        return conversationService.createConversation(currentUserId(token), resolvedTitle);
    }

    @DeleteMapping("/conversations")
    public Result deleteConversations(
            @RequestHeader(value = "Authorization", required = false) String token,
            @RequestBody(required = false) DeleteConversationsRequest request
    ) {
        List<Long> conversationIds = request == null || request.conversationIds() == null ? List.of() : request.conversationIds();
        return conversationService.deleteConversations(currentUserId(token), conversationIds);
    }

    @GetMapping("/conversations/{id}/messages")
    public List<MessageView> messages(
            @RequestHeader(value = "Authorization", required = false) String token,
            @PathVariable Long id
    ) {
        Long resolvedUserId = currentUserId(token);
        conversationService.checkOwner(resolvedUserId, id);
        return messageService.listMessages(id);
    }

    @PostMapping("/chat")
    public ChatResponse chat(
            @RequestHeader(value = "Authorization", required = false) String token,
            @RequestBody ChatRequest request
    ) {
        return chatService.ask(currentUserId(token), request);
    }

    private Long currentUserId(String token) {
        User user = authService.requireUser(token);
        return user.getId();
    }
}
