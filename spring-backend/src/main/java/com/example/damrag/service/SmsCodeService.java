package com.example.damrag.service;

import java.security.SecureRandom;
import java.time.Instant;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.stereotype.Service;

@Service
public class SmsCodeService {
    private static final long EXPIRE_SECONDS = 300;
    private final SecureRandom random = new SecureRandom();
    private final Map<String, CodeRecord> codeStore = new ConcurrentHashMap<>();

    public SmsCodeResult generate(String phone, String scene) {
        validatePhone(phone);

        String normalizedScene = normalizeScene(scene);
        String normalizedPhone = phone.trim();
        String code = String.format("%06d", random.nextInt(1_000_000));
        Instant expiresAt = Instant.now().plusSeconds(EXPIRE_SECONDS);

        codeStore.put(buildKey(normalizedPhone, normalizedScene), new CodeRecord(code, expiresAt));

        // Test environment: return the code directly.
        // In production, replace this with Aliyun/Tencent SMS API.
        return new SmsCodeResult("验证码已生成，测试环境直接返回", code, EXPIRE_SECONDS);
    }

    public void verify(String phone, String scene, String smsCode) {
        validatePhone(phone);

        if (smsCode == null || smsCode.isBlank()) {
            throw new IllegalArgumentException("SMS code is required.");
        }

        String normalizedScene = normalizeScene(scene);
        String normalizedPhone = phone.trim();
        String key = buildKey(normalizedPhone, normalizedScene);
        CodeRecord record = codeStore.get(key);

        if (record == null) {
            throw new IllegalArgumentException("Please request an SMS code first.");
        }

        if (Instant.now().isAfter(record.expiresAt())) {
            codeStore.remove(key);
            throw new IllegalArgumentException("SMS code has expired. Please request a new one.");
        }

        if (!record.code().equals(smsCode.trim())) {
            throw new IllegalArgumentException("验证码错误");
        }

        codeStore.remove(key);
    }

    private String buildKey(String phone, String scene) {
        return scene + ":" + phone.trim();
    }

    private String normalizeScene(String scene) {
        if (scene == null || scene.isBlank()) {
            return "login";
        }

        String value = scene.trim().toLowerCase();
        if (!value.equals("login") && !value.equals("register")) {
            return "login";
        }

        return value;
    }

    private void validatePhone(String phone) {
        if (phone == null || !phone.trim().matches("^1\\d{10}$")) {
            throw new IllegalArgumentException("Invalid phone number.");
        }
    }

    private record CodeRecord(String code, Instant expiresAt) {}

    public record SmsCodeResult(String message, String smsCode, long expireSeconds) {}
}