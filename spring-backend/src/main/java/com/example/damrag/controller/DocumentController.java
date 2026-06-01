package com.example.damrag.controller;

import com.example.damrag.model.KbDocument;
import com.example.damrag.model.User;
import com.example.damrag.repository.KbDocumentRepository;
import com.example.damrag.service.AuthService;
import com.example.damrag.service.RagClient;
import jakarta.annotation.PreDestroy;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
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
    private final ExecutorService ingestExecutor = Executors.newSingleThreadExecutor();

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
            document.setProcessStatus("等待入库");
            document = documentRepository.save(document);
            allDocuments.add(document);

            try {
                file.transferTo(storedPath);
                savedDocuments.add(document);
            } catch (Exception e) {
                document.setProcessStatus("处理失败");
                document.setErrorMessage(summarizeDiagnostic(e.getMessage()));
                documentRepository.save(document);
            }
        }

        if (!savedDocuments.isEmpty()) {
            ingestAsync(savedDocuments);
        }

        return allDocuments;
    }

    protected void deleteDocumentById(Long id) {
        KbDocument document = documentRepository.findById(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "文档不存在"));
        deleteDocument(document);
    }

    protected KbDocument retryDocumentById(Long id) {
        KbDocument document = documentRepository.findById(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "文档不存在"));
        Path storedPath = uploadDir.resolve(document.getStoredName()).toAbsolutePath().normalize();
        if (!Files.isRegularFile(storedPath)) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "原始文档文件不存在，请重新上传");
        }
        document.setProcessStatus("等待入库");
        document.setErrorMessage(null);
        KbDocument saved = documentRepository.save(document);
        ingestAsync(List.of(saved));
        return saved;
    }

    protected KbDocument updatePageOffsetAndRetry(Long id, Integer pageOffset) {
        KbDocument document = documentRepository.findById(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Document not found"));
        document.setPageOffset(pageOffset);
        documentRepository.save(document);
        return retryDocumentById(id);
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
        deleteVectorsAsync(document.getId());
    }

    private void ingestAsync(List<KbDocument> affectedDocuments) {
        ingestExecutor.submit(() -> {
            List<KbDocument> documentsToUpdate = reloadDocuments(affectedDocuments);
            for (KbDocument document : documentsToUpdate) {
                updateDocumentsStatus(List.of(document), "正在入库", null);
                try {
                    Path filePath = uploadDir.resolve(document.getStoredName()).toAbsolutePath().normalize();
                    ragClient.ingest(filePath, document.getId(), document.getUploadedBy(), true, document.getPageOffset());
                    updateDocumentsStatus(List.of(document), "已完成", null);
                } catch (Exception e) {
                    updateDocumentsStatus(List.of(document), "处理失败", e.getMessage());
                }
            }
        });
    }

    private void deleteVectorsAsync(Long documentId) {
        ingestExecutor.submit(() -> {
            try {
                ragClient.deleteDocument(documentId);
            } catch (Exception e) {
                System.err.println("Failed to delete RAG vectors for document " + documentId + ": " + e.getMessage());
            }
        });
    }

    private List<KbDocument> reloadDocuments(List<KbDocument> documents) {
        return documents.stream()
                .map(KbDocument::getId)
                .flatMap(id -> documentRepository.findById(id).stream())
                .toList();
    }

    private void updateDocumentsStatus(List<KbDocument> documents, String status, String errorMessage) {
        documents.forEach(document -> {
            document.setProcessStatus(status);
            document.setErrorMessage(summarizeDiagnostic(errorMessage));
            documentRepository.save(document);
        });
    }

    private String summarizeDiagnostic(String message) {
        if (message == null || message.length() <= 900) {
            return message;
        }
        return message.substring(0, 897) + "...";
    }

    @PreDestroy
    public void shutdownIngestExecutor() {
        ingestExecutor.shutdown();
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
