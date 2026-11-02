package com.socialapp.security;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.socialapp.dto.auth.LoginRequest;
import com.socialapp.dto.auth.PasswordChangeRequest;
import com.socialapp.dto.auth.SignupRequest;
import com.socialapp.entity.User;
import com.socialapp.repository.UserRepository;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
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
import org.springframework.test.web.servlet.MvcResult;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Base64;
import java.util.Date;

import static org.hamcrest.Matchers.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
@TestPropertySource(locations = "classpath:application-test.properties")
public class AdversarialSecurityTest {

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

    private static final String TEST_SECRET = "c29jaWFsYXBwLXNlY3JldC1rZXktZm9yLWp3dC1hdXRoZW50aWNhdGlvbi0yNTYtYml0cyE=";
    private static final String ATTACKER_SECRET = "YXR0YWNrZXItc2VjcmV0LWtleS1mb3Itand0LWF1dGhlbnRpY2F0aW9uLTI1Ni1iaXRzIQ==";

    @BeforeEach
    void setUp() {
        userRepository.deleteAll();
    }

    // =========================================================================
    // 1. JwtTokenProvider Adversarial Verification
    // =========================================================================

    @Test
    @DisplayName("JwtTokenProvider - Rejects expired tokens created in past")
    void testJwtExpiredTokenRejected() {
        JwtTokenProvider pastProvider = new JwtTokenProvider(TEST_SECRET, -5);
        String expiredToken = pastProvider.generateToken(1L, "victim");

        assertFalse(jwtTokenProvider.validateToken(expiredToken), "Expired token must be rejected");
    }

    @Test
    @DisplayName("JwtTokenProvider - Rejects payload-modified token with original signature")
    void testJwtPayloadTamperedRejected() {
        String originalToken = jwtTokenProvider.generateToken(100L, "originalUser");
        String[] parts = originalToken.split("\\.");
        assertEquals(3, parts.length, "JWT must have 3 parts");

        // Decode payload JSON, alter subject from 100 to 999, re-encode without resigning
        String payloadJson = new String(Base64.getUrlDecoder().decode(parts[1]), StandardCharsets.UTF_8);
        String tamperedPayloadJson = payloadJson.replace("\"sub\":\"100\"", "\"sub\":\"999\"");
        String tamperedPayloadBase64 = Base64.getUrlEncoder().withoutPadding()
                .encodeToString(tamperedPayloadJson.getBytes(StandardCharsets.UTF_8));

        String forgedToken = parts[0] + "." + tamperedPayloadBase64 + "." + parts[2];
        assertFalse(jwtTokenProvider.validateToken(forgedToken), "Token with modified payload must be rejected");
    }

    @Test
    @DisplayName("JwtTokenProvider - Rejects token signed with attacker secret key")
    void testJwtAttackerKeyRejected() {
        SecretKey attackerKey = Keys.hmacShaKeyFor(Base64.getDecoder().decode(ATTACKER_SECRET));
        Instant now = Instant.now();
        String forgedToken = Jwts.builder()
                .subject("100")
                .claim("username", "admin")
                .issuedAt(Date.from(now))
                .expiration(Date.from(now.plus(1, ChronoUnit.HOURS)))
                .signWith(attackerKey, Jwts.SIG.HS256)
                .compact();

        assertFalse(jwtTokenProvider.validateToken(forgedToken), "Token signed with wrong key must be rejected");
    }

    @Test
    @DisplayName("JwtTokenProvider - Rejects token with alg none")
    void testJwtAlgNoneRejected() {
        // Construct header: {"alg":"none","typ":"JWT"} -> base64
        String header = Base64.getUrlEncoder().withoutPadding()
                .encodeToString("{\"alg\":\"none\",\"typ\":\"JWT\"}".getBytes(StandardCharsets.UTF_8));
        String payload = Base64.getUrlEncoder().withoutPadding()
                .encodeToString("{\"sub\":\"100\",\"username\":\"hacker\"}".getBytes(StandardCharsets.UTF_8));
        String unsignedToken = header + "." + payload + ".";

        assertFalse(jwtTokenProvider.validateToken(unsignedToken), "Alg none token must be rejected");
    }

    @Test
    @DisplayName("JwtTokenProvider - Rejects malformed and garbage strings safely without throwing")
    void testJwtMalformedStrings() {
        assertFalse(jwtTokenProvider.validateToken(null));
        assertFalse(jwtTokenProvider.validateToken(""));
        assertFalse(jwtTokenProvider.validateToken("   "));
        assertFalse(jwtTokenProvider.validateToken("header.payload"));
        assertFalse(jwtTokenProvider.validateToken("header.payload.signature.extra"));
        assertFalse(jwtTokenProvider.validateToken("!@#$%^&*()_+=-"));
        assertFalse(jwtTokenProvider.validateToken("Bearer 12345"));
    }

    // =========================================================================
    // 2. SecurityConfig & JwtAuthFilter Protected Endpoint Enforcement
    // =========================================================================

    @Test
    @DisplayName("SecurityConfig - Protected endpoint /api/auth/me rejects missing token with 401 JSON")
    void testProtectedEndpointNoToken() throws Exception {
        MvcResult result = mockMvc.perform(get("/api/auth/me"))
                .andExpect(status().isUnauthorized())
                .andExpect(content().contentType(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.status").value(401))
                .andExpect(jsonPath("$.error").value("Unauthorized"))
                .andExpect(jsonPath("$.message").value("Invalid or expired token"))
                .andExpect(jsonPath("$.path").value("/api/auth/me"))
                .andExpect(jsonPath("$.timestamp").isNotEmpty())
                .andReturn();

        String body = result.getResponse().getContentAsString();
        assertFalse(body.contains("<html"), "Error response must not be HTML");
        assertFalse(body.contains("Exception"), "Error response must not leak Java stack trace");
    }

    @Test
    @DisplayName("SecurityConfig - Protected endpoint /api/auth/me rejects expired token with 401 JSON")
    void testProtectedEndpointExpiredToken() throws Exception {
        JwtTokenProvider pastProvider = new JwtTokenProvider(TEST_SECRET, -2);
        String expiredToken = pastProvider.generateToken(1L, "victim");

        mockMvc.perform(get("/api/auth/me")
                        .header("Authorization", "Bearer " + expiredToken))
                .andExpect(status().isUnauthorized())
                .andExpect(content().contentType(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.status").value(401))
                .andExpect(jsonPath("$.error").value("Unauthorized"))
                .andExpect(jsonPath("$.message").value("Invalid or expired token"))
                .andExpect(jsonPath("$.path").value("/api/auth/me"));
    }

    @Test
    @DisplayName("SecurityConfig - Protected endpoint /api/auth/me rejects tampered token with 401 JSON")
    void testProtectedEndpointTamperedToken() throws Exception {
        String token = jwtTokenProvider.generateToken(1L, "victim");
        String tampered = token + "corrupted";

        mockMvc.perform(get("/api/auth/me")
                        .header("Authorization", "Bearer " + tampered))
                .andExpect(status().isUnauthorized())
                .andExpect(content().contentType(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.status").value(401))
                .andExpect(jsonPath("$.error").value("Unauthorized"))
                .andExpect(jsonPath("$.message").value("Invalid or expired token"));
    }

    @Test
    @DisplayName("SecurityConfig - Protected endpoint rejects Basic auth header with 401 JSON")
    void testProtectedEndpointBasicAuthRejected() throws Exception {
        mockMvc.perform(get("/api/auth/me")
                        .header("Authorization", "Basic YWRtaW46cGFzc3dvcmQ="))
                .andExpect(status().isUnauthorized())
                .andExpect(content().contentType(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.status").value(401))
                .andExpect(jsonPath("$.error").value("Unauthorized"))
                .andExpect(jsonPath("$.message").value("Invalid or expired token"));
    }

    @Test
    @DisplayName("SecurityConfig - Arbitrary unauthenticated /api path rejects with 401 JSON")
    void testArbitraryProtectedPath() throws Exception {
        mockMvc.perform(get("/api/feed"))
                .andExpect(status().isUnauthorized())
                .andExpect(content().contentType(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.status").value(401))
                .andExpect(jsonPath("$.error").value("Unauthorized"))
                .andExpect(jsonPath("$.path").value("/api/feed"));
    }

    @Test
    @DisplayName("SecurityConfig - Token with non-numeric subject safely results in 401 JSON without crashing")
    void testProtectedEndpointNonNumericSubjectToken() throws Exception {
        SecretKey key = Keys.hmacShaKeyFor(Base64.getDecoder().decode(TEST_SECRET));
        Instant now = Instant.now();
        String stringSubToken = Jwts.builder()
                .subject("not-a-number")
                .claim("username", "admin")
                .issuedAt(Date.from(now))
                .expiration(Date.from(now.plus(1, ChronoUnit.HOURS)))
                .signWith(key, Jwts.SIG.HS256)
                .compact();

        mockMvc.perform(get("/api/auth/me")
                        .header("Authorization", "Bearer " + stringSubToken))
                .andExpect(status().isUnauthorized())
                .andExpect(content().contentType(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.status").value(401))
                .andExpect(jsonPath("$.error").value("Unauthorized"))
                .andExpect(jsonPath("$.message").value("Invalid or expired token"));
    }

    @Test
    @DisplayName("SecurityConfig - Public endpoint whitelist permits access without token")
    void testPublicEndpointsAccessibleWithoutAuth() throws Exception {
        // /api/auth/login and /api/auth/signup are public endpoints; invalid payload returns 400 Bad Request, NOT 401 Unauthorized
        mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.status").value(400));
    }

    // =========================================================================
    // 3. AuthService & AuthController Adversarial Verification
    // =========================================================================

    @Test
    @DisplayName("AuthService - Duplicate username with case variation returns 409 Conflict")
    void testDuplicateUsernameCaseInsensitive() throws Exception {
        userRepository.save(User.builder()
                .username("john_doe")
                .email("john@example.com")
                .passwordHash(passwordEncoder.encode("Password123"))
                .build());

        SignupRequest req = SignupRequest.builder()
                .username("John_Doe") // Uppercase variation
                .email("other@example.com")
                .password("Password123")
                .build();

        mockMvc.perform(post("/api/auth/signup")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.status").value(409))
                .andExpect(jsonPath("$.error").value("Conflict"))
                .andExpect(jsonPath("$.message").value("Username is already taken"));
    }

    @Test
    @DisplayName("AuthService - Duplicate email with case variation returns 409 Conflict")
    void testDuplicateEmailCaseInsensitive() throws Exception {
        userRepository.save(User.builder()
                .username("existing_user")
                .email("victim@example.com")
                .passwordHash(passwordEncoder.encode("Password123"))
                .build());

        SignupRequest req = SignupRequest.builder()
                .username("new_unique_user")
                .email("VICTIM@EXAMPLE.COM") // Uppercase variation
                .password("Password123")
                .build();

        mockMvc.perform(post("/api/auth/signup")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.status").value(409))
                .andExpect(jsonPath("$.error").value("Conflict"))
                .andExpect(jsonPath("$.message").value("Email is already in use"));
    }

    @Test
    @DisplayName("AuthService - User enumeration prevention: wrong password vs unknown username return IDENTICAL 401")
    void testUserEnumerationPreventionIdenticalResponse() throws Exception {
        userRepository.save(User.builder()
                .username("existing_account")
                .email("existing@example.com")
                .passwordHash(passwordEncoder.encode("CorrectPassword123"))
                .build());

        // 1. Existing user, wrong password
        LoginRequest wrongPwReq = LoginRequest.builder()
                .username("existing_account")
                .password("WrongPassword123")
                .build();

        MvcResult wrongPwResult = mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(wrongPwReq)))
                .andExpect(status().isUnauthorized())
                .andReturn();

        // 2. Unknown user
        LoginRequest unknownUserReq = LoginRequest.builder()
                .username("nonexistent_account")
                .password("AnyPassword123")
                .build();

        MvcResult unknownUserResult = mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(unknownUserReq)))
                .andExpect(status().isUnauthorized())
                .andReturn();

        // Compare JSON fields for status, error, and message
        JsonNode wrongPwJson = objectMapper.readTree(wrongPwResult.getResponse().getContentAsString());
        JsonNode unknownUserJson = objectMapper.readTree(unknownUserResult.getResponse().getContentAsString());

        assertEquals(401, wrongPwJson.get("status").asInt());
        assertEquals(401, unknownUserJson.get("status").asInt());
        assertEquals("Unauthorized", wrongPwJson.get("error").asText());
        assertEquals("Unauthorized", unknownUserJson.get("error").asText());
        assertEquals("Invalid username or password", wrongPwJson.get("message").asText());
        assertEquals("Invalid username or password", unknownUserJson.get("message").asText());
        assertEquals(wrongPwJson.get("message").asText(), unknownUserJson.get("message").asText());
    }

    @Test
    @DisplayName("AuthService - Password change: rejects incorrect old password with HTTP 400")
    void testPasswordChangeIncorrectOldPassword() throws Exception {
        User user = userRepository.save(User.builder()
                .username("alice_test")
                .email("alice@example.com")
                .passwordHash(passwordEncoder.encode("ValidOldPass1"))
                .build());

        String token = jwtTokenProvider.generateToken(user.getId(), user.getUsername());

        PasswordChangeRequest request = PasswordChangeRequest.builder()
                .oldPassword("IncorrectGuess99")
                .newPassword("NewValidPass2")
                .build();

        mockMvc.perform(put("/api/auth/password")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.status").value(400))
                .andExpect(jsonPath("$.error").value("Bad Request"))
                .andExpect(jsonPath("$.message").value("Old password is incorrect"));

        // Verify old password is still intact
        User reloaded = userRepository.findById(user.getId()).orElseThrow();
        assertTrue(passwordEncoder.matches("ValidOldPass1", reloaded.getPasswordHash()));
        assertFalse(passwordEncoder.matches("NewValidPass2", reloaded.getPasswordHash()));
    }

    @Test
    @DisplayName("AuthService - Password change: rejects weak new password with HTTP 400 and fieldErrors")
    void testPasswordChangeWeakNewPassword() throws Exception {
        User user = userRepository.save(User.builder()
                .username("bob_test")
                .email("bob@example.com")
                .passwordHash(passwordEncoder.encode("ValidOldPass1"))
                .build());

        String token = jwtTokenProvider.generateToken(user.getId(), user.getUsername());

        // Weak new password: only letters, no digits
        PasswordChangeRequest request = PasswordChangeRequest.builder()
                .oldPassword("ValidOldPass1")
                .newPassword("onlylettersnohumber")
                .build();

        mockMvc.perform(put("/api/auth/password")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.status").value(400))
                .andExpect(jsonPath("$.fieldErrors.newPassword").value("New password must contain at least one letter and one digit"));
    }

    @Test
    @DisplayName("AuthService - Access with valid token for deleted/non-existent user returns 404")
    void testMeUserNotFoundInDb() throws Exception {
        // Issue token for user id 999999 who does not exist in DB
        String ghostToken = jwtTokenProvider.generateToken(999999L, "ghost");

        mockMvc.perform(get("/api/auth/me")
                        .header("Authorization", "Bearer " + ghostToken))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.status").value(404))
                .andExpect(jsonPath("$.error").value("Not Found"))
                .andExpect(jsonPath("$.message").value("User not found with id: 999999"));
    }
}
