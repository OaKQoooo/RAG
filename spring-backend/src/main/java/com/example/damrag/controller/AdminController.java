package com.example.damrag.controller;

import com.example.damrag.dto.AuthDtos.UserView;
import com.example.damrag.dto.DocumentDtos.StatusRequest;
import com.example.damrag.model.KbDocument;
import com.example.damrag.model.User;
import com.example.damrag.repository.KbChunkRepository;
import com.example.damrag.repository.KbClauseRepository;
import com.example.damrag.repository.KbDocumentRepository;
import com.example.damrag.repository.UserRepository;
import com.example.damrag.service.AuthService;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/admin")
public class AdminController {
    private final KbDocumentRepository documentRepository;
    private final UserRepository userRepository;
    private final KbClauseRepository clauseRepository;
    private final KbChunkRepository chunkRepository;
    private final DocumentController documentController;
    private final AuthService authService;

    public AdminController(
            KbDocumentRepository documentRepository,
            UserRepository userRepository,
            KbClauseRepository clauseRepository,
            KbChunkRepository chunkRepository,
            DocumentController documentController,
            AuthService authService
    ) {
        this.documentRepository = documentRepository;
        this.userRepository = userRepository;
        this.clauseRepository = clauseRepository;
        this.chunkRepository = chunkRepository;
        this.documentController = documentController;
        this.authService = authService;
    }

    @GetMapping("/overview")
    public Map<String, Long> overview(@RequestHeader(value = "Authorization", required = false) String token) {
        requireAdmin(token);
        return Map.of(
                "documentCount", documentRepository.count(),
                "userCount", userRepository.count(),
                "clauseCount", clauseRepository.count(),
                "chunkCount", chunkRepository.count()
        );
    }

    @GetMapping("/documents")
    public List<KbDocument> documents(@RequestHeader(value = "Authorization", required = false) String token) {
        requireAdmin(token);
        return documentRepository.findAll()
                .stream()
                .sorted(Comparator.comparing(
                        KbDocument::getCreatedAt,
                        Comparator.nullsLast(Comparator.reverseOrder())
                ))
                .toList();
    }

    @PostMapping("/documents/upload")
    public List<KbDocument> uploadAdminDocuments(
            @RequestHeader(value = "Authorization", required = false) String token,
            @RequestParam("files") MultipartFile[] files
    ) {
        User admin = requireAdmin(token);
        return documentController.upload(files, admin.getId(), "admin", "public");
    }

    @DeleteMapping("/documents/{id}")
    public void deleteDocument(@RequestHeader(value = "Authorization", required = false) String token, @PathVariable Long id) {
        requireAdmin(token);
        documentController.deleteDocumentById(id);
    }

    @GetMapping("/users")
    public List<UserView> users(@RequestHeader(value = "Authorization", required = false) String token) {
        requireAdmin(token);
        return userRepository.findAll().stream().map(this::toView).toList();
    }

    @PatchMapping("/users/{id}/status")
    public UserView updateStatus(@RequestHeader(value = "Authorization", required = false) String token, @PathVariable Long id, @RequestBody StatusRequest request) {
        requireAdmin(token);
        User user = userRepository.findById(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "用户不存在"));
        user.setStatus(request.status());
        return toView(userRepository.save(user));
    }

    private UserView toView(User user) {
        return new UserView(
                user.getId(),
                user.getPhone(),
                user.getUsername(),
                user.getRole(),
                user.getStatus(),
                user.getAvatarUrl(),
                user.getTheme()
        );
    }

    private User requireAdmin(String token) {
        return authService.requireAdmin(token);
    }
}
