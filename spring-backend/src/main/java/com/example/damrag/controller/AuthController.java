package com.example.damrag.controller;

import com.example.damrag.dto.AuthDtos.AuthResponse;
import com.example.damrag.dto.AuthDtos.LoginRequest;
import com.example.damrag.dto.AuthDtos.LogoutResult;
import com.example.damrag.dto.AuthDtos.RegisterRequest;
import com.example.damrag.dto.AuthDtos.UserView;
import com.example.damrag.service.AuthService;
import java.util.Map;
import org.springframework.web.bind.annotation.*;
import com.example.damrag.dto.AuthDtos.SmsCodeRequest;
import com.example.damrag.dto.AuthDtos.SmsCodeResponse;
import com.example.damrag.service.SmsCodeService;

@RestController
@RequestMapping("/api/auth")
public class AuthController {
    private final AuthService authService;
    private final SmsCodeService smsCodeService;

    public AuthController(AuthService authService, SmsCodeService smsCodeService) {
        this.authService = authService;
        this.smsCodeService = smsCodeService;
    }

    @PostMapping("/register")
    public AuthResponse register(@RequestBody RegisterRequest request) {
        return authService.register(request);
    }

    @PostMapping("/login")
    public AuthResponse login(@RequestBody LoginRequest request) {
        return authService.login(request);
    }

    @PostMapping("/logout")
    public LogoutResult logout(@RequestHeader(value = "Authorization", required = false) String token) {
        return authService.logout(token);
    }

    @PostMapping("/sms-code")
    public SmsCodeResponse sendSmsCode(@RequestBody SmsCodeRequest request) {
        var result = smsCodeService.generate(request.phone(), request.scene());
        return new SmsCodeResponse(result.message(), result.smsCode(), result.expireSeconds());
    }

    @GetMapping("/current")
    public UserView currentUser(@RequestHeader(value = "Authorization", required = false) String token) {
        return authService.currentUser(token);
    }

    @GetMapping("/me")
    public UserView me(@RequestParam Long userId) {
        return authService.me(userId);
    }

    @PatchMapping("/me")
    public UserView updateMe(@RequestParam Long userId, @RequestBody Map<String, String> body) {
        return authService.updateMe(userId, body);
    }
}
