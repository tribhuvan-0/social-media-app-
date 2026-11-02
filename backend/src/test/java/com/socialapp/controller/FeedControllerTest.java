package com.socialapp.controller;

import com.socialapp.entity.Follow;
import com.socialapp.entity.Media;
import com.socialapp.entity.User;
import com.socialapp.entity.enums.MediaKind;
import com.socialapp.entity.enums.MediaType;
import com.socialapp.repository.FollowRepository;
import com.socialapp.repository.MediaRepository;
import com.socialapp.repository.UserRepository;
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
class FeedControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private MediaRepository mediaRepository;

    @Autowired
    private FollowRepository followRepository;

    @Autowired
    private PasswordEncoder passwordEncoder;

    @Autowired
    private JwtTokenProvider jwtTokenProvider;

    private User currentUser;
    private User followedUser;
    private User strangerUser;
    private String token;

    @BeforeEach
    void setUp() {
        mediaRepository.deleteAll();
        followRepository.deleteAll();
        userRepository.deleteAll();

        currentUser = userRepository.save(User.builder()
                .username("feed_me")
                .email("feed_me@test.com")
                .passwordHash(passwordEncoder.encode("Password123"))
                .build());

        followedUser = userRepository.save(User.builder()
                .username("feed_followed")
                .email("feed_followed@test.com")
                .passwordHash(passwordEncoder.encode("Password123"))
                .build());

        strangerUser = userRepository.save(User.builder()
                .username("feed_stranger")
                .email("feed_stranger@test.com")
                .passwordHash(passwordEncoder.encode("Password123"))
                .build());

        followRepository.save(Follow.builder()
                .followerId(currentUser.getId())
                .followingId(followedUser.getId())
                .createdAt(Instant.now())
                .build());

        token = jwtTokenProvider.generateToken(currentUser.getId(), currentUser.getUsername());
    }

    @Test
    @DisplayName("GET /api/feed - Returns POST and REEL from followed user and self newest first")
    void testFeedReturnsFollowedAndSelfNewestFirst() throws Exception {
        Instant now = Instant.now();

        // 1. Followed user's post (oldest)
        Media m1 = mediaRepository.save(Media.builder()
                .userId(followedUser.getId())
                .type(MediaType.POST)
                .mediaKind(MediaKind.IMAGE)
                .r2Key("POST/" + followedUser.getId() + "/1.jpg")
                .caption("Followed user post")
                .createdAt(now.minus(2, ChronoUnit.HOURS))
                .build());

        // 2. Stranger user's post (should NOT appear)
        mediaRepository.save(Media.builder()
                .userId(strangerUser.getId())
                .type(MediaType.POST)
                .mediaKind(MediaKind.IMAGE)
                .r2Key("POST/" + strangerUser.getId() + "/stranger.jpg")
                .caption("Stranger post")
                .createdAt(now.minus(1, ChronoUnit.HOURS))
                .build());

        // 3. Current user's own reel (newest)
        Media m3 = mediaRepository.save(Media.builder()
                .userId(currentUser.getId())
                .type(MediaType.REEL)
                .mediaKind(MediaKind.VIDEO)
                .r2Key("REEL/" + currentUser.getId() + "/myreel.mp4")
                .caption("My reel")
                .createdAt(now)
                .build());

        mockMvc.perform(get("/api/feed")
                        .header("Authorization", "Bearer " + token)
                        .param("page", "0")
                        .param("size", "10"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items", hasSize(2)))
                .andExpect(jsonPath("$.items[0].id", is(m3.getId().intValue())))
                .andExpect(jsonPath("$.items[1].id", is(m1.getId().intValue())))
                .andExpect(jsonPath("$.hasNext", is(false)));
    }

    @Test
    @DisplayName("GET /api/feed - Stories are excluded from feed")
    void testStoriesExcludedFromFeed() throws Exception {
        mediaRepository.save(Media.builder()
                .userId(followedUser.getId())
                .type(MediaType.STORY)
                .mediaKind(MediaKind.IMAGE)
                .r2Key("STORY/" + followedUser.getId() + "/story.jpg")
                .caption("My story")
                .expiresAt(Instant.now().plus(24, ChronoUnit.HOURS))
                .build());

        mockMvc.perform(get("/api/feed")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items", hasSize(0)))
                .andExpect(jsonPath("$.hasNext", is(false)));
    }

    @Test
    @DisplayName("GET /api/feed - Invalid page or size returns 400 Bad Request")
    void testFeedInvalidParameters() throws Exception {
        mockMvc.perform(get("/api/feed")
                        .header("Authorization", "Bearer " + token)
                        .param("page", "-1"))
                .andExpect(status().isBadRequest());

        mockMvc.perform(get("/api/feed")
                        .header("Authorization", "Bearer " + token)
                        .param("size", "0"))
                .andExpect(status().isBadRequest());

        mockMvc.perform(get("/api/feed")
                        .header("Authorization", "Bearer " + token)
                        .param("size", "51"))
                .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("GET /api/feed - Unauthenticated request returns 401")
    void testFeedUnauthenticated() throws Exception {
        mockMvc.perform(get("/api/feed"))
                .andExpect(status().isUnauthorized());
    }
}
