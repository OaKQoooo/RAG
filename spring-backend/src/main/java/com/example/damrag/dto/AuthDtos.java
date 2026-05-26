package com.example.damrag.dto;

import java.time.LocalDateTime;

public class AuthDtos {
    public record LoginRequest(String phone, String password, String smsCode, String loginType, String role) {}
    public record RegisterRequest(String phone, String smsCode, String username, String password, String confirmPassword) {}
    public record UserView(Long id, String phone, String username, String role, Integer status, String avatarUrl, String theme, LocalDateTime createdAt, LocalDateTime updatedAt) {}
    public record AuthResponse(String token, UserView user) {}
    public record LogoutResult(boolean success, String message) {}

    public record SmsCodeRequest(String phone, String scene) {}
    public record SmsCodeResponse(String message, String smsCode, long expireSeconds) {}
}
