package com.example.damrag.controller;

import com.example.damrag.dto.ActivityDtos.ActivityView;
import com.example.damrag.dto.AuthDtos.UserView;
import com.example.damrag.dto.DocumentDtos.StatusRequest;
import com.example.damrag.model.AdminActivity;
import com.example.damrag.model.KbDocument;
import com.example.damrag.model.User;
import com.example.damrag.repository.AdminActivityRepository;
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
    private final AdminActivityRepository activityRepository;
    private final DocumentController documentController;
    private final AuthService authService;

    public AdminController(
            KbDocumentRepository documentRepository,
            UserRepository userRepository,
            KbClauseRepository clauseRepository,
            KbChunkRepository chunkRepository,
            AdminActivityRepository activityRepository,
            DocumentController documentController,
            AuthService authService
    ) {
        this.documentRepository = documentRepository;
        this.userRepository = userRepository;
        this.clauseRepository = clauseRepository;
        this.chunkRepository = chunkRepository;
        this.activityRepository = activityRepository;
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

    @GetMapping("/activities")
    public List<ActivityView> activities(@RequestHeader(value = "Authorization", required = false) String token) {
        requireAdmin(token);
        return activityRepository.findTop20ByOrderByCreatedAtDesc()
                .stream()
                .map(this::toActivityView)
                .toList();
    }

    @PostMapping("/documents/upload")
    public List<KbDocument> uploadAdminDocuments(
            @RequestHeader(value = "Authorization", required = false) String token,
            @RequestParam("files") MultipartFile[] files
    ) {
        User admin = requireAdmin(token);
        List<KbDocument> documents = documentController.upload(files, admin.getId(), "admin", "public");
        documents.forEach(document -> logActivity(
                admin,
                "document_upload",
                "上传文档《" + document.getFileName() + "》，入库状态：" + document.getProcessStatus(),
                "document",
                document.getId()
        ));
        return documents;
    }

    @DeleteMapping("/documents/{id}")
    public void deleteDocument(@RequestHeader(value = "Authorization", required = false) String token, @PathVariable Long id) {
        User admin = requireAdmin(token);
        KbDocument document = documentRepository.findById(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "文档不存在"));
        documentController.deleteDocumentById(id);
        logActivity(
                admin,
                "document_delete",
                "删除文档《" + document.getFileName() + "》并重建知识库",
                "document",
                id
        );
    }

    @GetMapping("/users")
    public List<UserView> users(@RequestHeader(value = "Authorization", required = false) String token) {
        requireAdmin(token);
        return userRepository.findAll()
                .stream()
                .sorted(Comparator.comparing(
                        User::getCreatedAt,
                        Comparator.nullsLast(Comparator.reverseOrder())
                ))
                .map(this::toView)
                .toList();
    }

    @PatchMapping("/users/{id}/status")
    public UserView updateStatus(@RequestHeader(value = "Authorization", required = false) String token, @PathVariable Long id, @RequestBody StatusRequest request) {
        User admin = requireAdmin(token);
        if (admin.getId().equals(id)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "不能禁用当前登录的管理员账号");
        }
        if (request == null || request.status() == null || (request.status() != 0 && request.status() != 1)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "用户状态只能是 0 或 1");
        }
        User user = userRepository.findById(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "用户不存在"));
        user.setStatus(request.status());
        User saved = userRepository.save(user);
        String actionText = saved.getStatus() == 1 ? "启用" : "禁用";
        logActivity(
                admin,
                "user_status",
                actionText + "用户「" + displayName(saved) + "」",
                "user",
                saved.getId()
        );
        return toView(saved);
    }

    private void logActivity(User actor, String action, String message, String targetType, Long targetId) {
        AdminActivity activity = new AdminActivity();
        activity.setActorId(actor.getId());
        activity.setActorName(displayName(actor));
        activity.setActorRole(actor.getRole());
        activity.setAction(action);
        activity.setMessage(message);
        activity.setTargetType(targetType);
        activity.setTargetId(targetId);
        activityRepository.save(activity);
    }

    private ActivityView toActivityView(AdminActivity activity) {
        return new ActivityView(
                activity.getId(),
                activity.getActorId(),
                activity.getActorName(),
                activity.getActorRole(),
                activity.getAction(),
                activity.getMessage(),
                activity.getTargetType(),
                activity.getTargetId(),
                activity.getCreatedAt()
        );
    }

    private String displayName(User user) {
        if (user.getUsername() != null && !user.getUsername().isBlank()) {
            return user.getUsername();
        }
        if (user.getPhone() != null && !user.getPhone().isBlank()) {
            return user.getPhone();
        }
        return "用户" + user.getId();
    }

    private UserView toView(User user) {
        return new UserView(
                user.getId(),
                user.getPhone(),
                user.getUsername(),
                user.getRole(),
                user.getStatus(),
                user.getAvatarUrl(),
                user.getTheme(),
                user.getCreatedAt(),
                user.getUpdatedAt()
        );
    }

    private User requireAdmin(String token) {
        return authService.requireAdmin(token);
    }
}
