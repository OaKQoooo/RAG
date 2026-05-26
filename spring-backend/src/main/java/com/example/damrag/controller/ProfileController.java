package com.example.damrag.controller;

import com.example.damrag.dto.ProfileDtos.ChangePhoneRequest;
import com.example.damrag.dto.ProfileDtos.ChangePasswordRequest;
import com.example.damrag.dto.ProfileDtos.ProfileUpdateRequest;
import com.example.damrag.dto.ProfileDtos.Result;
import com.example.damrag.dto.ProfileDtos.UserProfile;
import com.example.damrag.model.User;
import com.example.damrag.service.AuthService;
import com.example.damrag.service.ProfileService;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/profile")
public class ProfileController {
    private final ProfileService profileService;
    private final AuthService authService;

    public ProfileController(ProfileService profileService, AuthService authService) {
        this.profileService = profileService;
        this.authService = authService;
    }

    @GetMapping
    public UserProfile getProfile(@RequestHeader(value = "Authorization", required = false) String token) {
        return profileService.getProfile(currentUserId(token));
    }

    @PatchMapping
    public UserProfile updateProfile(@RequestHeader(value = "Authorization", required = false) String token, @RequestBody ProfileUpdateRequest request) {
        return profileService.updateProfile(currentUserId(token), request);
    }

    @PostMapping("/phone")
    public UserProfile changePhone(@RequestHeader(value = "Authorization", required = false) String token, @RequestBody ChangePhoneRequest request) {
        return profileService.changePhone(currentUserId(token), request);
    }

    @PostMapping("/password")
    public Result changePassword(@RequestHeader(value = "Authorization", required = false) String token, @RequestBody ChangePasswordRequest request) {
        return profileService.changePassword(currentUserId(token), request);
    }

    @DeleteMapping("/conversations")
    public Result clearConversationHistory(@RequestHeader(value = "Authorization", required = false) String token) {
        return profileService.clearConversationHistory(currentUserId(token));
    }

    private Long currentUserId(String token) {
        User user = authService.requireUser(token);
        return user.getId();
    }
}
