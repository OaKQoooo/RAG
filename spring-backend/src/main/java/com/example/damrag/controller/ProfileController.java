package com.example.damrag.controller;

import com.example.damrag.dto.ProfileDtos.ChangePhoneRequest;
import com.example.damrag.dto.ProfileDtos.ChangePasswordRequest;
import com.example.damrag.dto.ProfileDtos.ProfileUpdateRequest;
import com.example.damrag.dto.ProfileDtos.Result;
import com.example.damrag.dto.ProfileDtos.UserProfile;
import com.example.damrag.service.ProfileService;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/profile")
public class ProfileController {
    private final ProfileService profileService;

    public ProfileController(ProfileService profileService) {
        this.profileService = profileService;
    }

    @GetMapping
    public UserProfile getProfile(@RequestParam Long userId) {
        return profileService.getProfile(userId);
    }

    @PatchMapping
    public UserProfile updateProfile(@RequestParam Long userId, @RequestBody ProfileUpdateRequest request) {
        return profileService.updateProfile(userId, request);
    }

    @PostMapping("/phone")
    public UserProfile changePhone(@RequestParam Long userId, @RequestBody ChangePhoneRequest request) {
        return profileService.changePhone(userId, request);
    }

    @PostMapping("/password")
    public Result changePassword(@RequestParam Long userId, @RequestBody ChangePasswordRequest request) {
        return profileService.changePassword(userId, request);
    }

    @DeleteMapping("/conversations")
    public Result clearConversationHistory(@RequestParam Long userId) {
        return profileService.clearConversationHistory(userId);
    }
}
