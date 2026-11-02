package com.socialapp.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.socialapp.dto.auth.LoginRequest;
import com.socialapp.dto.auth.PasswordChangeRequest;
import com.socialapp.dto.auth.SignupRequest;
import com.socialapp.entity.User;
import com.socialapp.repository.UserRepository;
import com.socialapp.security.JwtTokenProvider;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;

import static org.hamcrest.Matchers.*;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
@TestPropertySource(locations = "classpath:application-test.properties")
class AuthControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private PasswordEncoder passwordEncoder;

    @Autowired
    private JwtTokenProvider jwtTokenProvider;

    @BeforeEach
    void setUp() {
        userRepository.deleteAll();
    }

    @Test
    @DisplayName("POST /api/auth/signup - Successful registration returns 201 with token and user")
    void testSignupSuccess() throws Exception {
        SignupRequest request = SignupRequest.builder()
                .username("newuser")
                .email("newuser@example.com")
                .password("Password123")
                .build();

        mockMvc.perform(post("/api/auth/signup")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.token").isString())
                .andExpect(jsonPath("$.token").isNotEmpty())
                .andExpect(jsonPath("$.user.id").isNumber())
                .andExpect(jsonPath("$.user.username").value("newuser"))
                .andExpect(jsonPath("$.user.email").value("newuser@example.com"))
                .andExpect(jsonPath("$.user.isPrivate").value(false))
                .andExpect(jsonPath("$.user.notificationsEnabled").value(true));
    }

    @Test
    @DisplayName("POST /api/auth/signup - Duplicate username returns 409 Conflict")
    void testSignupDuplicateUsername() throws Exception {
        userRepository.save(User.builder()
                .username("existinguser")
                .email("first@example.com")
                .passwordHash(passwordEncoder.encode("Password123"))
                .build());

        SignupRequest request = SignupRequest.builder()
                .username("existinguser")
                .email("second@example.com")
                .password("Password123")
                .build();

        mockMvc.perform(post("/api/auth/signup")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.status").value(409))
                .andExpect(jsonPath("$.error").value("Conflict"))
                .andExpect(jsonPath("$.message").value("Username is already taken"));
    }

    @Test
    @DisplayName("POST /api/auth/signup - Duplicate email returns 409 Conflict")
    void testSignupDuplicateEmail() throws Exception {
        userRepository.save(User.builder()
                .username("userone")
                .email("shared@example.com")
                .passwordHash(passwordEncoder.encode("Password123"))
                .build());

        SignupRequest request = SignupRequest.builder()
                .username("usertwo")
                .email("shared@example.com")
                .password("Password123")
                .build();

        mockMvc.perform(post("/api/auth/signup")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.status").value(409))
                .andExpect(jsonPath("$.error").value("Conflict"))
                .andExpect(jsonPath("$.message").value("Email is already in use"));
    }

    @Test
    @DisplayName("POST /api/auth/signup - Invalid password returns 400 Bad Request with fieldErrors")
    void testSignupValidationFailure() throws Exception {
        SignupRequest request = SignupRequest.builder()
                .username("validuser")
                .email("valid@example.com")
                .password("short") // too short, < 8 chars and lacks letters/digits pattern
                .build();

        mockMvc.perform(post("/api/auth/signup")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.status").value(400))
                .andExpect(jsonPath("$.error").value("Bad Request"))
                .andExpect(jsonPath("$.fieldErrors.password").exists());
    }

    @Test
    @DisplayName("POST /api/auth/login - Successful credentials return 200 with token and user")
    void testLoginSuccess() throws Exception {
        userRepository.save(User.builder()
                .username("loginuser")
                .email("login@example.com")
                .passwordHash(passwordEncoder.encode("Password123"))
                .build());

        LoginRequest request = LoginRequest.builder()
                .username("loginuser")
                .password("Password123")
                .build();

        mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.token").isString())
                .andExpect(jsonPath("$.token").isNotEmpty())
                .andExpect(jsonPath("$.user.username").value("loginuser"))
                .andExpect(jsonPath("$.user.email").value("login@example.com"));
    }

    @Test
    @DisplayName("POST /api/auth/login - Invalid password returns 401 Unauthorized")
    void testLoginBadCredentials() throws Exception {
        userRepository.save(User.builder()
                .username("loginuser")
                .email("login@example.com")
                .passwordHash(passwordEncoder.encode("Password123"))
                .build());

        LoginRequest request = LoginRequest.builder()
                .username("loginuser")
                .password("WrongPassword999")
                .build();

        mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.status").value(401))
                .andExpect(jsonPath("$.error").value("Unauthorized"))
                .andExpect(jsonPath("$.message").value("Invalid username or password"));
    }

    @Test
    @DisplayName("POST /api/auth/login - Unknown username returns 401 Unauthorized with identical error")
    void testLoginUnknownUser() throws Exception {
        LoginRequest request = LoginRequest.builder()
                .username("nonexistent")
                .password("Password123")
                .build();

        mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.status").value(401))
                .andExpect(jsonPath("$.error").value("Unauthorized"))
                .andExpect(jsonPath("$.message").value("Invalid username or password"));
    }

    @Test
    @DisplayName("GET /api/auth/me - Authenticated user returns 200 with MeResponse")
    void testMeAuthenticated() throws Exception {
        User user = userRepository.save(User.builder()
                .username("meuser")
                .email("me@example.com")
                .passwordHash(passwordEncoder.encode("Password123"))
                .bio("Hello world")
                .build());

        String token = jwtTokenProvider.generateToken(user.getId(), user.getUsername());

        mockMvc.perform(get("/api/auth/me")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(user.getId()))
                .andExpect(jsonPath("$.username").value("meuser"))
                .andExpect(jsonPath("$.email").value("me@example.com"))
                .andExpect(jsonPath("$.bio").value("Hello world"));
    }

    @Test
    @DisplayName("GET /api/auth/me - Missing token returns 401 Unauthorized with standard error response")
    void testMeUnauthenticated() throws Exception {
        mockMvc.perform(get("/api/auth/me"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.status").value(401))
                .andExpect(jsonPath("$.error").value("Unauthorized"))
                .andExpect(jsonPath("$.message").value("Invalid or expired token"));
    }

    @Test
    @DisplayName("PUT /api/auth/password - Valid old password updates hash and returns 204")
    void testPasswordChangeSuccess() throws Exception {
        User user = userRepository.save(User.builder()
                .username("pwduser")
                .email("pwd@example.com")
                .passwordHash(passwordEncoder.encode("OldPassword123"))
                .build());

        String token = jwtTokenProvider.generateToken(user.getId(), user.getUsername());

        PasswordChangeRequest request = PasswordChangeRequest.builder()
                .oldPassword("OldPassword123")
                .newPassword("NewPassword456")
                .build();

        mockMvc.perform(put("/api/auth/password")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isNoContent());

        // Verify that the user can now authenticate with the new password
        User updated = userRepository.findById(user.getId()).orElseThrow();
        assertTrue(passwordEncoder.matches("NewPassword456", updated.getPasswordHash()));
    }

    @Test
    @DisplayName("PUT /api/auth/password - Wrong old password returns 400 Bad Request")
    void testPasswordChangeBadOldPassword() throws Exception {
        User user = userRepository.save(User.builder()
                .username("pwduser2")
                .email("pwd2@example.com")
                .passwordHash(passwordEncoder.encode("OldPassword123"))
                .build());

        String token = jwtTokenProvider.generateToken(user.getId(), user.getUsername());

        PasswordChangeRequest request = PasswordChangeRequest.builder()
                .oldPassword("IncorrectPassword123")
                .newPassword("NewPassword456")
                .build();

        mockMvc.perform(put("/api/auth/password")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.status").value(400))
                .andExpect(jsonPath("$.message").value("Old password is incorrect"));
    }
}
