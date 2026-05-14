package com.example.damrag.service;

import com.example.damrag.dto.AuthDtos.AuthResponse;
import com.example.damrag.dto.AuthDtos.LoginRequest;
import com.example.damrag.dto.AuthDtos.LogoutResult;
import com.example.damrag.dto.AuthDtos.RegisterRequest;
import com.example.damrag.dto.AuthDtos.UserView;
import com.example.damrag.model.User;
import com.example.damrag.repository.UserRepository;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

@Service
public class AuthService {
    private static final String PHONE_PATTERN = "^1[3-9]\\d{9}$";
    private static final String DEMO_SMS_CODE = "123456";

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;

    public AuthService(UserRepository userRepository, PasswordEncoder passwordEncoder) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
    }

    public AuthResponse register(RegisterRequest request) {
        String phone = normalizePhone(request.phone());
        if (!isValidPhone(phone)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "手机号格式不正确");
        }
        if (!isValidSmsCode(request.smsCode())) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "验证码错误或失效");
        }
        if (request.password() == null || request.password().isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "密码不能为空");
        }
        if (request.confirmPassword() != null && !request.password().equals(request.confirmPassword())) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "两次密码输入不一致");
        }
        if (request.password().length() < 6) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "密码至少6位");
        }
        if (userRepository.existsByPhone(phone)) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "该手机号已注册");
        }

        User user = new User();
        user.setPhone(phone);
        user.setUsername(displayName(request.username(), phone));
        user.setPasswordHash(passwordEncoder.encode(request.password()));
        user.setRole("user");
        user.setStatus(1);
        userRepository.save(user);
        return new AuthResponse(tokenFor(user), toView(user));
    }

    public AuthResponse login(LoginRequest request) {
        String phone = normalizePhone(request.phone());
        User user = userRepository.findByPhone(phone)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "手机号或登录凭证错误"));

        String loginType = request.loginType();
        if (loginType == null || loginType.isBlank()) {
            loginType = request.smsCode() == null || request.smsCode().isBlank() ? "password" : "sms";
        }
        if ("sms".equalsIgnoreCase(loginType) || "code".equalsIgnoreCase(loginType)) {
            if (!isValidSmsCode(request.smsCode())) {
                throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "验证码错误或失效");
            }
        } else if (request.password() == null || !passwordEncoder.matches(request.password(), user.getPasswordHash())) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "手机号或密码错误");
        }
        if (user.getStatus() != null && user.getStatus() == 0) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "账号已被禁用");
        }
        if (request.role() != null && !request.role().isBlank() && !request.role().equals(user.getRole())) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "角色不匹配");
        }
        return new AuthResponse(tokenFor(user), toView(user));
    }

    public UserView currentUser(String token) {
        return toView(validateToken(token));
    }

    public LogoutResult logout(String token) {
        validateToken(token);
        return new LogoutResult(true, "已退出登录");
    }

    public User validateToken(String token) {
        Long userId = userIdFromToken(token);
        return userRepository.findById(userId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "登录已失效"));
    }

    public boolean checkPermission(User loginUser, String resource) {
        if (loginUser == null || loginUser.getStatus() == null || loginUser.getStatus() == 0) {
            return false;
        }
        return "admin".equals(loginUser.getRole()) || resource == null || resource.isBlank() || "user".equals(resource);
    }

    public UserView me(Long userId) {
        return userRepository.findById(userId)
                .map(this::toView)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "用户不存在"));
    }

    public UserView updateMe(Long userId, Map<String, String> body) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "用户不存在"));
        if (body.containsKey("username")) {
            user.setUsername(displayName(body.get("username"), user.getPhone()));
        }
        if (body.containsKey("avatarUrl")) {
            user.setAvatarUrl(body.get("avatarUrl"));
        }
        if (body.containsKey("theme")) {
            user.setTheme(body.get("theme"));
        }
        return toView(userRepository.save(user));
    }

    private String tokenFor(User user) {
        return "local-" + user.getId() + "-" + System.currentTimeMillis();
    }

    private Long userIdFromToken(String token) {
        String value = token == null ? "" : token.trim();
        if (value.startsWith("Bearer ")) {
            value = value.substring("Bearer ".length()).trim();
        }
        String[] parts = value.split("-");
        if (parts.length < 3 || !"local".equals(parts[0])) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "登录令牌无效");
        }
        try {
            return Long.valueOf(parts[1]);
        } catch (NumberFormatException ex) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "登录令牌无效");
        }
    }

    private String normalizePhone(String phone) {
        return phone == null ? "" : phone.trim();
    }

    private boolean isValidPhone(String phone) {
        return phone != null && phone.matches(PHONE_PATTERN);
    }

    private boolean isValidSmsCode(String smsCode) {
        return DEMO_SMS_CODE.equals(smsCode);
    }

    private String displayName(String username, String phone) {
        if (username != null && !username.isBlank()) {
            return username.trim();
        }
        return "用户" + phone.substring(phone.length() - 4);
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
}
