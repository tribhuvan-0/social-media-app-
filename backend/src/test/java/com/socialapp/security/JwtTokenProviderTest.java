package com.socialapp.security;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class JwtTokenProviderTest {

    private JwtTokenProvider jwtTokenProvider;
    private static final String TEST_SECRET = "c29jaWFsYXBwLXNlY3JldC1rZXktZm9yLWp3dC1hdXRoZW50aWNhdGlvbi0yNTYtYml0cyE=";

    @BeforeEach
    void setUp() {
        jwtTokenProvider = new JwtTokenProvider(TEST_SECRET, 24);
    }

    @Test
    @DisplayName("Should generate valid token and extract subject and claims correctly")
    void testGenerateAndValidateToken() {
        Long userId = 101L;
        String username = "testuser";

        String token = jwtTokenProvider.generateToken(userId, username);

        assertNotNull(token);
        assertTrue(jwtTokenProvider.validateToken(token));
        assertEquals(userId, jwtTokenProvider.getUserId(token));
        assertEquals(username, jwtTokenProvider.getUsername(token));
    }

    @Test
    @DisplayName("Should reject token when expired")
    void testExpiredToken() {
        // Create provider with negative expiration
        JwtTokenProvider expiredProvider = new JwtTokenProvider(TEST_SECRET, -1);
        String token = expiredProvider.generateToken(202L, "expireduser");

        assertFalse(jwtTokenProvider.validateToken(token));
    }

    @Test
    @DisplayName("Should reject tampered token with altered payload or signature")
    void testTamperedToken() {
        String token = jwtTokenProvider.generateToken(303L, "tamperuser");

        // Tamper with the signature by appending an arbitrary character
        String tamperedToken = token + "xyz";

        assertFalse(jwtTokenProvider.validateToken(tamperedToken));
    }

    @Test
    @DisplayName("Should return false for null, blank, or malformed tokens")
    void testInvalidTokenFormats() {
        assertFalse(jwtTokenProvider.validateToken(null));
        assertFalse(jwtTokenProvider.validateToken(""));
        assertFalse(jwtTokenProvider.validateToken("   "));
        assertFalse(jwtTokenProvider.validateToken("not-a-valid-jwt-token"));
    }
}
