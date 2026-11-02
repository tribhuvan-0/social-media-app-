package com.socialapp.security;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.io.Decoders;
import io.jsonwebtoken.security.Keys;
import jakarta.annotation.PostConstruct;
import jakarta.servlet.http.HttpServletRequest;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Date;

@Slf4j
@Component
public class JwtTokenProvider {

    @Value("${app.jwt.secret:c29jaWFsYXBwLXNlY3JldC1rZXktZm9yLWp3dC1hdXRoZW50aWNhdGlvbi0yNTYtYml0cyE=}")
    private String jwtSecret;

    @Value("${app.jwt.expiry-hours:168}")
    private long jwtExpiryHours;

    private SecretKey key;

    public JwtTokenProvider() {
    }

    public JwtTokenProvider(String jwtSecret, long jwtExpiryHours) {
        this.jwtSecret = jwtSecret;
        this.jwtExpiryHours = jwtExpiryHours;
        init();
    }

    @PostConstruct
    public void init() {
        if (jwtSecret == null || jwtSecret.isBlank()) {
            throw new IllegalArgumentException("JWT secret must not be blank");
        }
        try {
            byte[] decoded = Decoders.BASE64.decode(jwtSecret);
            if (decoded.length >= 32) {
                this.key = Keys.hmacShaKeyFor(decoded);
                return;
            }
        } catch (Exception ignored) {
            // Not valid Base64, fallback to UTF-8 bytes
        }

        byte[] keyBytes = jwtSecret.getBytes(StandardCharsets.UTF_8);
        if (keyBytes.length < 32) {
            byte[] padded = new byte[32];
            System.arraycopy(keyBytes, 0, padded, 0, Math.min(keyBytes.length, 32));
            this.key = Keys.hmacShaKeyFor(padded);
        } else {
            this.key = Keys.hmacShaKeyFor(keyBytes);
        }
    }

    public String generateToken(Long userId, String username) {
        Instant now = Instant.now();
        Instant expiry = now.plus(jwtExpiryHours, ChronoUnit.HOURS);

        return Jwts.builder()
                .subject(String.valueOf(userId))
                .claim("username", username)
                .issuedAt(Date.from(now))
                .expiration(Date.from(expiry))
                .signWith(key, Jwts.SIG.HS256)
                .compact();
    }

    public boolean validateToken(String token) {
        if (!StringUtils.hasText(token)) {
            return false;
        }
        try {
            Jwts.parser()
                    .verifyWith(key)
                    .build()
                    .parseSignedClaims(token);
            return true;
        } catch (JwtException | IllegalArgumentException e) {
            log.warn("Invalid JWT token: {}", e.getMessage());
            return false;
        }
    }

    public Claims getClaims(String token) {
        return Jwts.parser()
                .verifyWith(key)
                .build()
                .parseSignedClaims(token)
                .getPayload();
    }

    public Long getUserId(String token) {
        return Long.parseLong(getClaims(token).getSubject());
    }

    public String getUsername(String token) {
        return getClaims(token).get("username", String.class);
    }

    public String resolveToken(HttpServletRequest request) {
        String bearerToken = request.getHeader("Authorization");
        if (StringUtils.hasText(bearerToken) && bearerToken.startsWith("Bearer ")) {
            return bearerToken.substring(7);
        }
        return null;
    }
}
