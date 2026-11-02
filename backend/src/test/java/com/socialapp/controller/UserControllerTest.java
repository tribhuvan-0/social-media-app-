package com.socialapp.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.socialapp.dto.user.UpdateProfileRequest;
import com.socialapp.dto.user.UpdateSettingsRequest;
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

import static org.hamcrest.Matchers.*;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
@TestPropertySource(locations = "classpath:application-test.properties")
class UserControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private FollowRepository followRepository;

    @Autowired
    private FollowRequestRepository followRequestRepository;

    @Autowired
    private MediaRepository mediaRepository;

    @Autowired
    private PasswordEncoder passwordEncoder;

    @Autowired
    private JwtTokenProvider jwtTokenProvider;

    private User alice;
    private User bobPublic;
    private User charliePrivate;
    private String aliceToken;

    @BeforeEach
    void setUp() {
        followRequestRepository.deleteAll();
        followRepository.deleteAll();
        mediaRepository.deleteAll();
        userRepository.deleteAll();

        alice = userRepository.save(User.builder()
                .username("alice_user")
                .email("alice@test.com")
                .passwordHash(passwordEncoder.encode("Password123"))
                .isPrivate(false)
                .build());

        bobPublic = userRepository.save(User.builder()
                .username("bob_public")
                .email("bob@test.com")
                .passwordHash(passwordEncoder.encode("Password123"))
                .isPrivate(false)
                .build());

        charliePrivate = userRepository.save(User.builder()
                .username("charlie_priv")
                .email("charlie@test.com")
                .passwordHash(passwordEncoder.encode("Password123"))
                .isPrivate(true)
                .build());

        aliceToken = jwtTokenProvider.generateToken(alice.getId(), alice.getUsername());
    }

    @Test
    @DisplayName("GET /api/users/{id}/profile - Profile stats and flags")
    void testGetUserProfile() throws Exception {
        mediaRepository.save(Media.builder()
                .userId(bobPublic.getId())
                .type(MediaType.POST)
                .mediaKind(MediaKind.IMAGE)
                .r2Key("POST/" + bobPublic.getId() + "/p1.jpg")
                .build());

        mockMvc.perform(get("/api/users/" + bobPublic.getId() + "/profile")
                        .header("Authorization", "Bearer " + aliceToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id", is(bobPublic.getId().intValue())))
                .andExpect(jsonPath("$.isMe", is(false)))
                .andExpect(jsonPath("$.isPrivate", is(false)))
                .andExpect(jsonPath("$.canView", is(true)))
                .andExpect(jsonPath("$.postCount", is(1)))
                .andExpect(jsonPath("$.followerCount", is(0)));
    }

    @Test
    @DisplayName("GET /api/users/{id}/posts - Private user grid returns 403 to non-followers")
    void testGetPrivateUserPostsGrid() throws Exception {
        mediaRepository.save(Media.builder()
                .userId(charliePrivate.getId())
                .type(MediaType.POST)
                .mediaKind(MediaKind.IMAGE)
                .r2Key("POST/" + charliePrivate.getId() + "/c1.jpg")
                .build());

        mockMvc.perform(get("/api/users/" + charliePrivate.getId() + "/posts")
                        .header("Authorization", "Bearer " + aliceToken))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.message", containsString("This account is private")));
    }

    @Test
    @DisplayName("GET /api/users/suggested - Returns suggested accounts excluding self")
    void testGetSuggestedUsers() throws Exception {
        mockMvc.perform(get("/api/users/suggested")
                        .header("Authorization", "Bearer " + aliceToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items", hasSize(greaterThanOrEqualTo(1))))
                .andExpect(jsonPath("$.items[*].id", not(hasItem(alice.getId().intValue()))));
    }

    @Test
    @DisplayName("POST /api/users/{id}/follow - Self-follow rejected (400), public follows immediately, private requests")
    void testFollowUserFlows() throws Exception {
        // 1. Self-follow rejected (400)
        mockMvc.perform(post("/api/users/" + alice.getId() + "/follow")
                        .header("Authorization", "Bearer " + aliceToken))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message", containsString("Cannot follow yourself")));

        // 2. Public user follow -> following: true, requested: false
        mockMvc.perform(post("/api/users/" + bobPublic.getId() + "/follow")
                        .header("Authorization", "Bearer " + aliceToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.following", is(true)))
                .andExpect(jsonPath("$.requested", is(false)))
                .andExpect(jsonPath("$.followerCount", is(1)));

        assertTrue(followRepository.existsByFollowerIdAndFollowingId(alice.getId(), bobPublic.getId()));

        // 3. Private user follow -> following: false, requested: true
        mockMvc.perform(post("/api/users/" + charliePrivate.getId() + "/follow")
                        .header("Authorization", "Bearer " + aliceToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.following", is(false)))
                .andExpect(jsonPath("$.requested", is(true)));

        assertTrue(followRequestRepository.existsByRequesterIdAndTargetId(alice.getId(), charliePrivate.getId()));

        // 4. Unfollow cancels request or deletes follow
        mockMvc.perform(delete("/api/users/" + charliePrivate.getId() + "/follow")
                        .header("Authorization", "Bearer " + aliceToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.following", is(false)))
                .andExpect(jsonPath("$.requested", is(false)));

        assertFalse(followRequestRepository.existsByRequesterIdAndTargetId(alice.getId(), charliePrivate.getId()));
    }

    @Test
    @DisplayName("PUT /api/users/me/settings - Switching private to public auto-accepts pending requests")
    void testSwitchingPrivateToPublicAutoAccepts() throws Exception {
        // Set charlie to have pending request from alice
        followRequestRepository.save(new FollowRequest(alice.getId(), charliePrivate.getId(), Instant.now()));

        String charlieToken = jwtTokenProvider.generateToken(charliePrivate.getId(), charliePrivate.getUsername());

        UpdateSettingsRequest updateReq = UpdateSettingsRequest.builder()
                .isPrivate(false)
                .notificationsEnabled(true)
                .build();

        mockMvc.perform(put("/api/users/me/settings")
                        .header("Authorization", "Bearer " + charlieToken)
                        .contentType(org.springframework.http.MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(updateReq)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.isPrivate", is(false)));

        // Request must now be promoted to genuine Follow
        assertTrue(followRepository.existsByFollowerIdAndFollowingId(alice.getId(), charliePrivate.getId()));
        assertFalse(followRequestRepository.existsByRequesterIdAndTargetId(alice.getId(), charliePrivate.getId()));
    }

    @Test
    @DisplayName("PUT /api/users/me - Update profile bio and username")
    void testUpdateProfile() throws Exception {
        UpdateProfileRequest req = UpdateProfileRequest.builder()
                .username("alice_updated")
                .bio("New cool bio")
                .build();

        mockMvc.perform(put("/api/users/me")
                        .header("Authorization", "Bearer " + aliceToken)
                        .contentType(org.springframework.http.MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.username", is("alice_updated")))
                .andExpect(jsonPath("$.bio", is("New cool bio")));
    }
}
