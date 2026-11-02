package com.socialapp.service;

import com.socialapp.dto.auth.*;
import com.socialapp.entity.User;
import com.socialapp.exception.BadRequestException;
import com.socialapp.exception.ConflictException;
import com.socialapp.exception.NotFoundException;
import com.socialapp.exception.UnauthorizedException;
import com.socialapp.mapper.UserMapper;
import com.socialapp.repository.UserRepository;
import com.socialapp.security.JwtTokenProvider;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;

@Slf4j
@Service
@RequiredArgsConstructor
public class AuthService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtTokenProvider jwtTokenProvider;
    private final UserMapper userMapper;

    @Transactional
    public AuthResponse signup(SignupRequest request) {
        String normalizedUsername = request.getUsername().trim().toLowerCase();
        String normalizedEmail = request.getEmail().trim().toLowerCase();

        if (userRepository.existsByUsername(normalizedUsername)) {
            throw new ConflictException("Username is already taken");
        }
        if (userRepository.existsByEmail(normalizedEmail)) {
            throw new ConflictException("Email is already in use");
        }

        User user = User.builder()
                .username(normalizedUsername)
                .email(normalizedEmail)
                .passwordHash(passwordEncoder.encode(request.getPassword()))
                .isPrivate(false)
                .notificationsEnabled(true)
                .createdAt(Instant.now())
                .build();

        User savedUser = userRepository.save(user);
        String token = jwtTokenProvider.generateToken(savedUser.getId(), savedUser.getUsername());

        log.info("Registered new user: {}", savedUser.getUsername());
        return AuthResponse.builder()
                .token(token)
                .user(userMapper.toMeResponse(savedUser))
                .build();
    }

    @Transactional(readOnly = true)
    public AuthResponse login(LoginRequest request) {
        String normalizedUsername = request.getUsername().trim().toLowerCase();

        User user = userRepository.findByUsername(normalizedUsername)
                .orElseThrow(() -> new UnauthorizedException("Invalid username or password"));

        if (!passwordEncoder.matches(request.getPassword(), user.getPasswordHash())) {
            log.warn("Invalid login attempt for username: {}", normalizedUsername);
            throw new UnauthorizedException("Invalid username or password");
        }

        String token = jwtTokenProvider.generateToken(user.getId(), user.getUsername());
        log.info("User logged in: {}", user.getUsername());

        return AuthResponse.builder()
                .token(token)
                .user(userMapper.toMeResponse(user))
                .build();
    }

    @Transactional(readOnly = true)
    public MeResponse getMe(Long userId) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new NotFoundException("User not found with id: " + userId));

        return userMapper.toMeResponse(user);
    }

    @Transactional
    public void changePassword(Long userId, PasswordChangeRequest request) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new NotFoundException("User not found with id: " + userId));

        if (!passwordEncoder.matches(request.getOldPassword(), user.getPasswordHash())) {
            throw new BadRequestException("Old password is incorrect");
        }

        user.setPasswordHash(passwordEncoder.encode(request.getNewPassword()));
        userRepository.save(user);
        log.info("Password changed for user id: {}", userId);
    }
}
