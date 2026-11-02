package com.socialapp.controller;

import com.socialapp.entity.FollowRequest;
import com.socialapp.entity.User;
import com.socialapp.repository.FollowRepository;
import com.socialapp.repository.FollowRequestRepository;
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

import static org.hamcrest.Matchers.*;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
@TestPropertySource(locations = "classpath:application-test.properties")
class FollowRequestControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private FollowRepository followRepository;

    @Autowired
    private FollowRequestRepository followRequestRepository;

    @Autowired
    private PasswordEncoder passwordEncoder;

    @Autowired
    private JwtTokenProvider jwtTokenProvider;

    private User target;
    private User requester;
    private String targetToken;

    @BeforeEach
    void setUp() {
        followRequestRepository.deleteAll();
        followRepository.deleteAll();
        userRepository.deleteAll();

        target = userRepository.save(User.builder()
                .username("target_user")
                .email("target@test.com")
                .passwordHash(passwordEncoder.encode("Password123"))
                .isPrivate(true)
                .build());

        requester = userRepository.save(User.builder()
                .username("requester_user")
                .email("requester@test.com")
                .passwordHash(passwordEncoder.encode("Password123"))
                .isPrivate(false)
                .build());

        targetToken = jwtTokenProvider.generateToken(target.getId(), target.getUsername());
    }

    @Test
    @DisplayName("GET & POST /api/follow-requests - List inbound, accept, and decline")
    void testFollowRequestsFlow() throws Exception {
        followRequestRepository.save(new FollowRequest(requester.getId(), target.getId(), Instant.now()));

        // 1. List inbound requests
        mockMvc.perform(get("/api/follow-requests")
                        .header("Authorization", "Bearer " + targetToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items", hasSize(1)))
                .andExpect(jsonPath("$.items[0].id", is(requester.getId().intValue())));

        // 2. Accept follow request
        mockMvc.perform(post("/api/follow-requests/" + requester.getId() + "/accept")
                        .header("Authorization", "Bearer " + targetToken))
                .andExpect(status().isNoContent());

        assertTrue(followRepository.existsByFollowerIdAndFollowingId(requester.getId(), target.getId()));
        assertFalse(followRequestRepository.existsByRequesterIdAndTargetId(requester.getId(), target.getId()));

        // 3. Second accept returns 404 (already handled)
        mockMvc.perform(post("/api/follow-requests/" + requester.getId() + "/accept")
                        .header("Authorization", "Bearer " + targetToken))
                .andExpect(status().isNotFound());
    }

    @Test
    @DisplayName("POST /api/follow-requests/{userId}/decline - Decline deletes request")
    void testDeclineFollowRequest() throws Exception {
        followRequestRepository.save(new FollowRequest(requester.getId(), target.getId(), Instant.now()));

        mockMvc.perform(post("/api/follow-requests/" + requester.getId() + "/decline")
                        .header("Authorization", "Bearer " + targetToken))
                .andExpect(status().isNoContent());

        assertFalse(followRepository.existsByFollowerIdAndFollowingId(requester.getId(), target.getId()));
        assertFalse(followRequestRepository.existsByRequesterIdAndTargetId(requester.getId(), target.getId()));
    }
}
