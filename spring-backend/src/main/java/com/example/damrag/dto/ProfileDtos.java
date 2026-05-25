package com.example.damrag.dto;

public class ProfileDtos {
    public record UserProfile(Long id, String phone, String username, String role, Integer status, String avatarUrl, String theme) {}
    public record ProfileUpdateRequest(String username, String avatarUrl, String theme) {}
    public record ChangePhoneRequest(String oldPhoneSmsCode, String newPhone, String newPhoneSmsCode) {}
    public record ChangePasswordRequest(String oldPassword, String newPassword, String confirmPassword) {}
    public record Result(boolean success, String message) {}
}
