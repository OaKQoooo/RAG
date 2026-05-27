package com.example.damrag.controller;

import com.example.damrag.model.KbDocument;
import com.example.damrag.model.User;
import com.example.damrag.repository.KbDocumentRepository;
import com.example.damrag.service.AuthService;
import com.example.damrag.service.RagClient;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/documents")
public class DocumentController {
    private final KbDocumentRepository documentRepository;
    private final RagClient ragClient;
    private final AuthService authService;
    private final Path uploadDir;

    public DocumentController(
            KbDocumentRepository documentRepository,
            RagClient ragClient,
            AuthService authService,
            @Value("${rag.upload-dir}") String uploadDir
    ) {
        this.documentRepository = documentRepository;
        this.ragClient = ragClient;
        this.authService = authService;
        this.uploadDir = Path.of(uploadDir);
    }

    @GetMapping("/my")
    public List<KbDocument> myDocuments(@RequestHeader(value = "Authorization", required = false) String token) {
        return documentRepository.findByUploadedByOrderByCreatedAtDesc(currentUserId(token));
    }

    @GetMapping("/visible")
    public List<KbDocument> visibleDocuments(@RequestHeader(value = "Authorization", required = false) String token) {
        return documentRepository.findByVisibilityOrUploadedByOrderByCreatedAtDesc("public", currentUserId(token));
    }

    @PostMapping("/upload")
    public List<KbDocument> uploadUserDocuments(
            @RequestHeader(value = "Authorization", required = false) String token,
            @RequestParam(defaultValue = "private") String visibility,
            @RequestParam("files") MultipartFile[] files
    ) {
        return upload(files, currentUserId(token), "user", visibility);
    }

    @DeleteMapping("/{id}")
    public void deleteUserDocument(@RequestHeader(value = "Authorization", required = false) String token, @PathVariable Long id) {
        Long userId = currentUserId(token);
        KbDocument document = documentRepository.findById(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "文档不存在"));
        if (!userId.equals(document.getUploadedBy())) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "无权删除该文档");
        }
        deleteDocument(document);
    }

    protected List<KbDocument> upload(MultipartFile[] files, Long userId, String role, String visibility) {
        try {
            Files.createDirectories(uploadDir);
        } catch (IOException e) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "无法创建上传目录");
        }

        List<KbDocument> allDocuments = new ArrayList<>();
        List<KbDocument> savedDocuments = new ArrayList<>();

        for (MultipartFile file : files) {
            if (file.isEmpty() || file.getOriginalFilename() == null || !file.getOriginalFilename().toLowerCase().endsWith(".pdf")) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "仅支持非空 PDF 文件");
            }

            String storedName = storedName(userId, role, file.getOriginalFilename());
            Path storedPath = uploadDir.resolve(storedName);
            KbDocument document = new KbDocument();
            document.setFileName(file.getOriginalFilename());
            document.setStoredName(storedName);
            document.setUploadedBy(userId);
            document.setUploadRole(role);
            document.setVisibility(visibility);
            document.setProcessStatus("正在解析");
            document = documentRepository.save(document);
            allDocuments.add(document);

            try {
                file.transferTo(storedPath);
                savedDocuments.add(document);
            } catch (Exception e) {
                document.setProcessStatus("处理失败");
                document.setErrorMessage(e.getMessage());
                documentRepository.save(document);
            }
        }

        if (!savedDocuments.isEmpty()) {
            try {
                List<KbDocument> activeDocuments = documentRepository.findAll()
                        .stream()
                        .filter(doc -> doc.getStoredName() != null && !doc.getStoredName().isBlank())
                        .toList();

                ragClient.rebuild(activeDocuments, uploadDir);

                savedDocuments.forEach(document -> {
                    document.setProcessStatus("已完成");
                    document.setErrorMessage(null);
                    documentRepository.save(document);
                });
            } catch (Exception e) {
                savedDocuments.forEach(document -> {
                    document.setProcessStatus("处理失败");
                    document.setErrorMessage(e.getMessage());
                    documentRepository.save(document);
                });
            }
        }

        return allDocuments;
    }

    protected void deleteDocumentById(Long id) {
        KbDocument document = documentRepository.findById(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "文档不存在"));
        deleteDocument(document);
    }

    private void deleteDocument(KbDocument document) {
        if (document.getStoredName() != null && !document.getStoredName().isBlank()) {
            Path storedPath = uploadDir.resolve(document.getStoredName()).normalize();
            if (storedPath.startsWith(uploadDir.normalize())) {
                try {
                    Files.deleteIfExists(storedPath);
                } catch (IOException e) {
                    throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "删除文档文件失败");
                }
            }
        }
        documentRepository.delete(document);

        List<KbDocument> activeDocuments = documentRepository.findAll()
                .stream()
                .filter(doc -> doc.getStoredName() != null && !doc.getStoredName().isBlank())
                .toList();

        ragClient.rebuild(activeDocuments, uploadDir);
    }

    private String storedName(Long userId, String role, String originalName) {
        String safe = originalName.replaceAll("[\\\\/:*?\"<>|\\s]+", "_");
        String stamp = DateTimeFormatter.ofPattern("yyyyMMddHHmmss").format(java.time.LocalDateTime.now());
        return role + "_" + userId + "_" + stamp + "_" + safe;
    }

    private Long currentUserId(String token) {
        User user = authService.requireUser(token);
        return user.getId();
    }
}
