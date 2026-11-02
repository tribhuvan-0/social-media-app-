package com.socialapp.controller;

import com.socialapp.entity.*;
import com.socialapp.entity.enums.MediaKind;
import com.socialapp.entity.enums.MediaType;
import com.socialapp.repository.*;
import com.socialapp.security.JwtTokenProvider;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;

import java.time.Instant;
import java.time.temporal.ChronoUnit;

import static org.hamcrest.Matchers.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
@TestPropertySource(locations = "classpath:application-test.properties")
class ReelsControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private MediaRepository mediaRepository;

    @Autowired
    private MediaTagRepository mediaTagRepository;

    @Autowired
    private MediaViewRepository mediaViewRepository;

    @Autowired
    private UserInterestRepository userInterestRepository;

    @Autowired
    private PasswordEncoder passwordEncoder;

    @Autowired
    private JwtTokenProvider jwtTokenProvider;

    private User currentUser;
    private User creator1;
    private User creator2;
    private String token;

    @BeforeEach
    void setUp() {
        mediaViewRepository.deleteAll();
        userInterestRepository.deleteAll();
        mediaTagRepository.deleteAll();
        mediaRepository.deleteAll();
        userRepository.deleteAll();

        currentUser = userRepository.save(User.builder()
                .username("reels_me")
                .email("reels_me@test.com")
                .passwordHash(passwordEncoder.encode("Password123"))
                .build());

        creator1 = userRepository.save(User.builder()
                .username("creator_one")
                .email("creator_one@test.com")
                .passwordHash(passwordEncoder.encode("Password123"))
                .build());

        creator2 = userRepository.save(User.builder()
                .username("creator_two")
                .email("creator_two@test.com")
                .passwordHash(passwordEncoder.encode("Password123"))
                .build());

        token = jwtTokenProvider.generateToken(currentUser.getId(), currentUser.getUsername());
    }

    @Test
    @DisplayName("GET /api/reels - Returns recommended reels and respects exclude list")
    void testReelsRecommendationAndExclude() throws Exception {
        Media r1 = mediaRepository.save(Media.builder()
                .userId(creator1.getId())
                .type(MediaType.REEL)
                .mediaKind(MediaKind.VIDEO)
                .r2Key("REEL/" + creator1.getId() + "/1.mp4")
                .caption("Reel 1 #nature")
                .createdAt(Instant.now().minus(2, ChronoUnit.HOURS))
                .build());

        Media r2 = mediaRepository.save(Media.builder()
                .userId(creator2.getId())
                .type(MediaType.REEL)
                .mediaKind(MediaKind.VIDEO)
                .r2Key("REEL/" + creator2.getId() + "/2.mp4")
                .caption("Reel 2 #gaming")
                .createdAt(Instant.now().minus(1, ChronoUnit.HOURS))
                .build());

        // My own reel should NOT be returned
        mediaRepository.save(Media.builder()
                .userId(currentUser.getId())
                .type(MediaType.REEL)
                .mediaKind(MediaKind.VIDEO)
                .r2Key("REEL/" + currentUser.getId() + "/my.mp4")
                .caption("My own reel")
                .createdAt(Instant.now())
                .build());

        // Normal get returns both creators' reels
        mockMvc.perform(get("/api/reels")
                        .header("Authorization", "Bearer " + token)
                        .param("size", "5"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items", hasSize(2)));

        // Exclude r1
        mockMvc.perform(get("/api/reels")
                        .header("Authorization", "Bearer " + token)
                        .param("size", "5")
                        .param("exclude", String.valueOf(r1.getId())))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items", hasSize(1)))
                .andExpect(jsonPath("$.items[0].id", is(r2.getId().intValue())));
    }

    @Test
    @DisplayName("GET /api/reels - Invalid size returns 400 Bad Request")
    void testReelsInvalidSize() throws Exception {
        mockMvc.perform(get("/api/reels")
                        .header("Authorization", "Bearer " + token)
                        .param("size", "0"))
                .andExpect(status().isBadRequest());

        mockMvc.perform(get("/api/reels")
                        .header("Authorization", "Bearer " + token)
                        .param("size", "25"))
                .andExpect(status().isBadRequest());
    }
}
