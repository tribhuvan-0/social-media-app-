package com.socialapp.controller;

import com.socialapp.entity.Follow;
import com.socialapp.entity.Media;
import com.socialapp.entity.StoryView;
import com.socialapp.entity.User;
import com.socialapp.entity.enums.MediaKind;
import com.socialapp.entity.enums.MediaType;
import com.socialapp.repository.FollowRepository;
import com.socialapp.repository.MediaRepository;
import com.socialapp.repository.StoryViewRepository;
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
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
@TestPropertySource(locations = "classpath:application-test.properties")
class StoriesControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private MediaRepository mediaRepository;

    @Autowired
    private FollowRepository followRepository;

    @Autowired
    private StoryViewRepository storyViewRepository;

    @Autowired
    private PasswordEncoder passwordEncoder;

    @Autowired
    private JwtTokenProvider jwtTokenProvider;

    private User currentUser;
    private User followedUser1;
    private User followedUser2;
    private String token;

    @BeforeEach
    void setUp() {
        storyViewRepository.deleteAll();
        mediaRepository.deleteAll();
        followRepository.deleteAll();
        userRepository.deleteAll();

        currentUser = userRepository.save(User.builder()
                .username("story_me")
                .email("story_me@test.com")
                .passwordHash(passwordEncoder.encode("Password123"))
                .build());

        followedUser1 = userRepository.save(User.builder()
                .username("story_f1")
                .email("story_f1@test.com")
                .passwordHash(passwordEncoder.encode("Password123"))
                .build());

        followedUser2 = userRepository.save(User.builder()
                .username("story_f2")
                .email("story_f2@test.com")
                .passwordHash(passwordEncoder.encode("Password123"))
                .build());

        followRepository.save(new Follow(currentUser.getId(), followedUser1.getId(), Instant.now()));
        followRepository.save(new Follow(currentUser.getId(), followedUser2.getId(), Instant.now()));

        token = jwtTokenProvider.generateToken(currentUser.getId(), currentUser.getUsername());
    }

    @Test
    @DisplayName("GET /api/stories - Groups active stories with self first, then unseen, then seen")
    void testStoriesGroupingAndOrder() throws Exception {
        Instant now = Instant.now();

        // 1. My active story
        mediaRepository.save(Media.builder()
                .userId(currentUser.getId())
                .type(MediaType.STORY)
                .mediaKind(MediaKind.IMAGE)
                .r2Key("STORY/" + currentUser.getId() + "/my.jpg")
                .expiresAt(now.plus(12, ChronoUnit.HOURS))
                .createdAt(now.minus(2, ChronoUnit.HOURS))
                .build());

        // 2. Followed user 1 active story (unseen)
        mediaRepository.save(Media.builder()
                .userId(followedUser1.getId())
                .type(MediaType.STORY)
                .mediaKind(MediaKind.IMAGE)
                .r2Key("STORY/" + followedUser1.getId() + "/f1.jpg")
                .expiresAt(now.plus(10, ChronoUnit.HOURS))
                .createdAt(now.minus(1, ChronoUnit.HOURS))
                .build());

        // 3. Followed user 2 active story (already seen)
        Media seenStory = mediaRepository.save(Media.builder()
                .userId(followedUser2.getId())
                .type(MediaType.STORY)
                .mediaKind(MediaKind.IMAGE)
                .r2Key("STORY/" + followedUser2.getId() + "/f2.jpg")
                .expiresAt(now.plus(15, ChronoUnit.HOURS))
                .createdAt(now.minus(3, ChronoUnit.HOURS))
                .build());

        storyViewRepository.save(new StoryView(currentUser.getId(), seenStory.getId(), now.minus(1, ChronoUnit.HOURS)));

        mockMvc.perform(get("/api/stories")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items", hasSize(3)))
                // 1st group must be current user
                .andExpect(jsonPath("$.items[0].user.id", is(currentUser.getId().intValue())))
                // 2nd group must be followedUser1 (hasUnseen = true)
                .andExpect(jsonPath("$.items[1].user.id", is(followedUser1.getId().intValue())))
                .andExpect(jsonPath("$.items[1].hasUnseen", is(true)))
                // 3rd group must be followedUser2 (hasUnseen = false)
                .andExpect(jsonPath("$.items[2].user.id", is(followedUser2.getId().intValue())))
                .andExpect(jsonPath("$.items[2].hasUnseen", is(false)));
    }

    @Test
    @DisplayName("POST /api/stories/{id}/seen - Marks story seen idempotently and returns 204")
    void testMarkStorySeenIdempotent() throws Exception {
        Media story = mediaRepository.save(Media.builder()
                .userId(followedUser1.getId())
                .type(MediaType.STORY)
                .mediaKind(MediaKind.IMAGE)
                .r2Key("STORY/" + followedUser1.getId() + "/seen.jpg")
                .expiresAt(Instant.now().plus(20, ChronoUnit.HOURS))
                .createdAt(Instant.now().minus(1, ChronoUnit.HOURS))
                .build());

        mockMvc.perform(post("/api/stories/" + story.getId() + "/seen")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isNoContent());

        assertTrue(storyViewRepository.existsByUserIdAndMediaId(currentUser.getId(), story.getId()));

        // Second call should also return 204 idempotently
        mockMvc.perform(post("/api/stories/" + story.getId() + "/seen")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isNoContent());
    }

    @Test
    @DisplayName("POST /api/stories/{id}/seen - Expired story or non-story returns 404")
    void testMarkStorySeenExpiredOrInvalid() throws Exception {
        Media expiredStory = mediaRepository.save(Media.builder()
                .userId(followedUser1.getId())
                .type(MediaType.STORY)
                .mediaKind(MediaKind.IMAGE)
                .r2Key("STORY/" + followedUser1.getId() + "/exp.jpg")
                .expiresAt(Instant.now().minus(1, ChronoUnit.HOURS))
                .build());

        Media regularPost = mediaRepository.save(Media.builder()
                .userId(followedUser1.getId())
                .type(MediaType.POST)
                .mediaKind(MediaKind.IMAGE)
                .r2Key("POST/" + followedUser1.getId() + "/post.jpg")
                .build());

        mockMvc.perform(post("/api/stories/" + expiredStory.getId() + "/seen")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isNotFound());

        mockMvc.perform(post("/api/stories/" + regularPost.getId() + "/seen")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isNotFound());

        mockMvc.perform(post("/api/stories/99999/seen")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isNotFound());
    }
}
