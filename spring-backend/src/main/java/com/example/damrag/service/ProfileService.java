package com.example.damrag.service;

import com.example.damrag.dto.ProfileDtos.ChangePhoneRequest;
import com.example.damrag.dto.ProfileDtos.ChangePasswordRequest;
import com.example.damrag.dto.ProfileDtos.ProfileUpdateRequest;
import com.example.damrag.dto.ProfileDtos.Result;
import com.example.damrag.dto.ProfileDtos.UserProfile;
import com.example.damrag.model.QaConversation;
import com.example.damrag.model.QaMessage;
import com.example.damrag.model.User;
import com.example.damrag.repository.MessageReferenceRepository;
import com.example.damrag.repository.QaConversationRepository;
import com.example.damrag.repository.QaMessageRepository;
import com.example.damrag.repository.UserRepository;
import jakarta.transaction.Transactional;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

@Service
public class ProfileService {
    private static final String PHONE_PATTERN = "^1[3-9]\\d{9}$";

    private final UserRepository userRepository;
    private final QaConversationRepository conversationRepository;
    private final QaMessageRepository messageRepository;
    private final MessageReferenceRepository referenceRepository;
    private final PasswordEncoder passwordEncoder;
    private final SmsCodeService smsCodeService;

    public ProfileService(
            UserRepository userRepository,
            QaConversationRepository conversationRepository,
            QaMessageRepository messageRepository,
            MessageReferenceRepository referenceRepository,
            PasswordEncoder passwordEncoder,
            SmsCodeService smsCodeService
    ) {
        this.userRepository = userRepository;
        this.conversationRepository = conversationRepository;
        this.messageRepository = messageRepository;
        this.referenceRepository = referenceRepository;
        this.passwordEncoder = passwordEncoder;
        this.smsCodeService = smsCodeService;
    }

    public UserProfile getProfile(Long userId) {
        return toProfile(findUser(userId));
    }

    public UserProfile updateProfile(Long userId, ProfileUpdateRequest request) {
        validateProfile(request);
        User user = findUser(userId);
        if (request.username() != null) {
            user.setUsername(displayName(request.username(), user.getPhone()));
        }
        if (request.avatarUrl() != null) {
            user.setAvatarUrl(request.avatarUrl().trim());
        }
        if (request.theme() != null) {
            user.setTheme(normalizeTheme(request.theme()));
        }
        return toProfile(userRepository.save(user));
    }

    public UserProfile changePhone(Long userId, ChangePhoneRequest request) {
        if (request == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "手机号换绑参数不能为空");
        }
        User user = findUser(userId);
        String newPhone = normalizePhone(request.newPhone());
        if (!isValidPhone(newPhone)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "新手机号格式不正确");
        }
        if (newPhone.equals(user.getPhone())) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "新手机号不能与原手机号相同");
        }
        if (userRepository.existsByPhone(newPhone)) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "新手机号已被注册");
        }

        verifySmsCode(user.getPhone(), "login", request.oldPhoneSmsCode(), "原手机号验证码错误或失效");
        verifySmsCode(newPhone, "register", request.newPhoneSmsCode(), "新手机号验证码错误或失效");

        user.setPhone(newPhone);
        return toProfile(userRepository.save(user));
    }

    public Result changePassword(Long userId, ChangePasswordRequest request) {
        if (request == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "密码参数不能为空");
        }

        User user = findUser(userId);
        String oldPassword = request.oldPassword() == null ? "" : request.oldPassword();
        String newPassword = request.newPassword() == null ? "" : request.newPassword();
        String confirmPassword = request.confirmPassword() == null ? "" : request.confirmPassword();

        if (oldPassword.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "原密码不能为空");
        }
        if (!passwordEncoder.matches(oldPassword, user.getPasswordHash())) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "原密码错误");
        }
        if (newPassword.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "新密码不能为空");
        }
        if (newPassword.length() < 6) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "新密码至少6位");
        }
        if (!newPassword.equals(confirmPassword)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "两次新密码输入不一致");
        }
        if (passwordEncoder.matches(newPassword, user.getPasswordHash())) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "新密码不能与原密码相同");
        }

        user.setPasswordHash(passwordEncoder.encode(newPassword));
        userRepository.save(user);
        return new Result(true, "密码已修改，请使用新密码登录");
    }

    @Transactional
    public Result clearConversationHistory(Long userId) {
        findUser(userId);
        List<QaConversation> conversations = conversationRepository.findByUserIdOrderByUpdatedAtDesc(userId);
        List<Long> conversationIds = conversations.stream().map(QaConversation::getId).toList();
        if (!conversationIds.isEmpty()) {
            List<Long> messageIds = messageRepository.findByConversationIdIn(conversationIds)
                    .stream()
                    .map(QaMessage::getId)
                    .toList();
            if (!messageIds.isEmpty()) {
                referenceRepository.deleteByMessageIdIn(messageIds);
            }
            messageRepository.deleteByConversationIdIn(conversationIds);
        }
        conversationRepository.deleteByUserId(userId);
        return new Result(true, "会话历史已清空");
    }

    private void validateProfile(ProfileUpdateRequest request) {
        if (request.username() != null && request.username().trim().length() > 50) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "用户名长度不能超过50个字符");
        }
        if (request.avatarUrl() != null && request.avatarUrl().trim().length() > 500) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "头像地址过长");
        }
        if (request.theme() != null) {
            normalizeTheme(request.theme());
        }
    }

    private User findUser(Long userId) {
        return userRepository.findById(userId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "用户不存在"));
    }

    private String normalizeTheme(String theme) {
        String value = theme == null ? "light" : theme.trim().toLowerCase();
        if (!"light".equals(value) && !"dark".equals(value)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "主题参数无效");
        }
        return value;
    }

    private String normalizePhone(String phone) {
        return phone == null ? "" : phone.trim();
    }

    private boolean isValidPhone(String phone) {
        return phone != null && phone.matches(PHONE_PATTERN);
    }

    private void verifySmsCode(String phone, String scene, String smsCode, String message) {
        try {
            smsCodeService.verify(phone, scene, smsCode);
        } catch (IllegalArgumentException ex) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, message);
        }
    }

    private String displayName(String username, String phone) {
        if (username != null && !username.isBlank()) {
            return username.trim();
        }
        return "用户" + phone.substring(phone.length() - 4);
    }

    private UserProfile toProfile(User user) {
        return new UserProfile(
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
