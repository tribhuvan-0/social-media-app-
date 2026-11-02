package com.socialapp.controller;

import com.socialapp.dto.auth.*;
import com.socialapp.security.CurrentUser;
import com.socialapp.security.CustomUserDetails;
import com.socialapp.security.SecurityUtils;
import com.socialapp.service.AuthService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
public class AuthController {

    private final AuthService authService;

    @PostMapping("/signup")
    public ResponseEntity<AuthResponse> signup(@Valid @RequestBody SignupRequest request) {
        AuthResponse response = authService.signup(request);
        return ResponseEntity.status(HttpStatus.CREATED).body(response);
    }

    @PostMapping("/login")
    public ResponseEntity<AuthResponse> login(@Valid @RequestBody LoginRequest request) {
        AuthResponse response = authService.login(request);
        return ResponseEntity.ok(response);
    }

    @GetMapping("/me")
    public ResponseEntity<MeResponse> me(@CurrentUser CustomUserDetails userDetails) {
        Long userId = userDetails != null ? userDetails.getId() : SecurityUtils.getCurrentUserId();
        MeResponse response = authService.getMe(userId);
        return ResponseEntity.ok(response);
    }

    @PutMapping("/password")
    public ResponseEntity<Void> changePassword(@CurrentUser CustomUserDetails userDetails,
                                               @Valid @RequestBody PasswordChangeRequest request) {
        Long userId = userDetails != null ? userDetails.getId() : SecurityUtils.getCurrentUserId();
        authService.changePassword(userId, request);
        return ResponseEntity.noContent().build();
    }
}
