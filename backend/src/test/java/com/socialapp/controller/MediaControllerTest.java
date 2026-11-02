package com.socialapp.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.socialapp.dto.media.AddCommentRequest;
import com.socialapp.dto.media.ViewEventRequest;
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
import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
@TestPropertySource(locations = "classpath:application-test.properties")
class MediaControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private MediaRepository mediaRepository;

    @Autowired
    private LikeRepository likeRepository;

    @Autowired
    private CommentRepository commentRepository;

    @Autowired
    private ShareRepository shareRepository;

    @Autowired
    private MediaViewRepository mediaViewRepository;

    @Autowired
    private MediaTagRepository mediaTagRepository;

    @Autowired
    private FollowRepository followRepository;

    @Autowired
    private PasswordEncoder passwordEncoder;

    @Autowired
    private JwtTokenProvider jwtTokenProvider;

    private User owner;
    private User viewer;
    private User privateUser;
    private String ownerToken;
    private String viewerToken;

    @BeforeEach
    void setUp() {
        commentRepository.deleteAll();
        likeRepository.deleteAll();
        shareRepository.deleteAll();
        mediaViewRepository.deleteAll();
        mediaTagRepository.deleteAll();
        mediaRepository.deleteAll();
        followRepository.deleteAll();
        userRepository.deleteAll();

        owner = userRepository.save(User.builder()
                .username("media_owner")
                .email("media_owner@test.com")
                .passwordHash(passwordEncoder.encode("Password123"))
                .isPrivate(false)
                .build());

        viewer = userRepository.save(User.builder()
                .username("media_viewer")
                .email("media_viewer@test.com")
                .passwordHash(passwordEncoder.encode("Password123"))
                .isPrivate(false)
                .build());

        privateUser = userRepository.save(User.builder()
                .username("media_private")
                .email("media_private@test.com")
                .passwordHash(passwordEncoder.encode("Password123"))
                .isPrivate(true)
                .build());

        ownerToken = jwtTokenProvider.generateToken(owner.getId(), owner.getUsername());
        viewerToken = jwtTokenProvider.generateToken(viewer.getId(), viewer.getUsername());
    }

    @Test
    @DisplayName("GET /api/media/{id} - Public media accessible; private media non-follower gets 403")
    void testGetMediaPrivacy() throws Exception {
        Media publicPost = mediaRepository.save(Media.builder()
                .userId(owner.getId())
                .type(MediaType.POST)
                .mediaKind(MediaKind.IMAGE)
                .r2Key("POST/" + owner.getId() + "/public.jpg")
                .caption("Public post #fun")
                .build());

        Media privatePost = mediaRepository.save(Media.builder()
                .userId(privateUser.getId())
                .type(MediaType.POST)
                .mediaKind(MediaKind.IMAGE)
                .r2Key("POST/" + privateUser.getId() + "/secret.jpg")
                .caption("Secret post #shh")
                .build());

        // Viewer can access public media
        mockMvc.perform(get("/api/media/" + publicPost.getId())
                        .header("Authorization", "Bearer " + viewerToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id", is(publicPost.getId().intValue())))
                .andExpect(jsonPath("$.caption", is("Public post #fun")));

        // Viewer cannot access private user media (403 Forbidden)
        mockMvc.perform(get("/api/media/" + privatePost.getId())
                        .header("Authorization", "Bearer " + viewerToken))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.message", containsString("This account is private")));

        // Non-existent media returns 404
        mockMvc.perform(get("/api/media/99999")
                        .header("Authorization", "Bearer " + viewerToken))
                .andExpect(status().isNotFound());
    }

    @Test
    @DisplayName("DELETE /api/media/{id} - Owner can delete; non-owner gets 403")
    void testDeleteMediaOwnership() throws Exception {
        Media post = mediaRepository.save(Media.builder()
                .userId(owner.getId())
                .type(MediaType.POST)
                .mediaKind(MediaKind.IMAGE)
                .r2Key("POST/" + owner.getId() + "/del.jpg")
                .build());

        // Non-owner gets 403
        mockMvc.perform(delete("/api/media/" + post.getId())
                        .header("Authorization", "Bearer " + viewerToken))
                .andExpect(status().isForbidden());

        // Owner gets 204 No Content
        mockMvc.perform(delete("/api/media/" + post.getId())
                        .header("Authorization", "Bearer " + ownerToken))
                .andExpect(status().isNoContent());

        assertFalse(mediaRepository.existsById(post.getId()));
    }

    @Test
    @DisplayName("POST & DELETE /api/media/{id}/like - Idempotent like toggle with atomic counter")
    void testLikeAndUnlikeIdempotent() throws Exception {
        Media post = mediaRepository.save(Media.builder()
                .userId(owner.getId())
                .type(MediaType.POST)
                .mediaKind(MediaKind.IMAGE)
                .r2Key("POST/" + owner.getId() + "/like.jpg")
                .likeCount(0)
                .build());

        // 1. First like: increments likeCount to 1
        mockMvc.perform(post("/api/media/" + post.getId() + "/like")
                        .header("Authorization", "Bearer " + viewerToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.liked", is(true)))
                .andExpect(jsonPath("$.likeCount", is(1)));

        // 2. Duplicate like: idempotent, keeps likeCount 1
        mockMvc.perform(post("/api/media/" + post.getId() + "/like")
                        .header("Authorization", "Bearer " + viewerToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.liked", is(true)))
                .andExpect(jsonPath("$.likeCount", is(1)));

        // 3. Unlike: decrements likeCount to 0
        mockMvc.perform(delete("/api/media/" + post.getId() + "/like")
                        .header("Authorization", "Bearer " + viewerToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.liked", is(false)))
                .andExpect(jsonPath("$.likeCount", is(0)));

        // 4. Duplicate unlike: idempotent, floors at 0
        mockMvc.perform(delete("/api/media/" + post.getId() + "/like")
                        .header("Authorization", "Bearer " + viewerToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.liked", is(false)))
                .andExpect(jsonPath("$.likeCount", is(0)));
    }

    @Test
    @DisplayName("POST /api/media/{id}/share - Records share and increments shareCount")
    void testShareMedia() throws Exception {
        Media post = mediaRepository.save(Media.builder()
                .userId(owner.getId())
                .type(MediaType.POST)
                .mediaKind(MediaKind.IMAGE)
                .r2Key("POST/" + owner.getId() + "/share.jpg")
                .shareCount(0)
                .build());

        mockMvc.perform(post("/api/media/" + post.getId() + "/share")
                        .header("Authorization", "Bearer " + viewerToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.shareCount", is(1)))
                .andExpect(jsonPath("$.shareUrl", containsString("/m/" + post.getId())));
    }

    @Test
    @DisplayName("POST /api/media/{id}/view - Records view telemetry; ignored for own media and STORY")
    void testRecordView() throws Exception {
        Media reel = mediaRepository.save(Media.builder()
                .userId(owner.getId())
                .type(MediaType.REEL)
                .mediaKind(MediaKind.VIDEO)
                .r2Key("REEL/" + owner.getId() + "/v.mp4")
                .viewCount(0)
                .build());

        Media story = mediaRepository.save(Media.builder()
                .userId(owner.getId())
                .type(MediaType.STORY)
                .mediaKind(MediaKind.IMAGE)
                .r2Key("STORY/" + owner.getId() + "/s.jpg")
                .build());

        ViewEventRequest viewReq = ViewEventRequest.builder()
                .watchMs(15000L)
                .durationMs(15000L)
                .completed(true)
                .build();

        // 1. Viewer watching reel -> recorded
        mockMvc.perform(post("/api/media/" + reel.getId() + "/view")
                        .header("Authorization", "Bearer " + viewerToken)
                        .contentType(org.springframework.http.MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(viewReq)))
                .andExpect(status().isNoContent());

        assertEquals(1, mediaViewRepository.countByUserId(viewer.getId()));

        // 2. Owner watching own reel -> ignored (no error, returns 204, no new row)
        mockMvc.perform(post("/api/media/" + reel.getId() + "/view")
                        .header("Authorization", "Bearer " + ownerToken)
                        .contentType(org.springframework.http.MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(viewReq)))
                .andExpect(status().isNoContent());

        assertEquals(0, mediaViewRepository.countByUserId(owner.getId()));

        // 3. Watching story -> ignored
        mockMvc.perform(post("/api/media/" + story.getId() + "/view")
                        .header("Authorization", "Bearer " + viewerToken)
                        .contentType(org.springframework.http.MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(viewReq)))
                .andExpect(status().isNoContent());

        assertEquals(1, mediaViewRepository.countByUserId(viewer.getId()));
    }

    @Test
    @DisplayName("Comments lifecycle - Add, List, Delete by author and media owner")
    void testCommentsLifecycle() throws Exception {
        Media post = mediaRepository.save(Media.builder()
                .userId(owner.getId())
                .type(MediaType.POST)
                .mediaKind(MediaKind.IMAGE)
                .r2Key("POST/" + owner.getId() + "/comm.jpg")
                .commentCount(0)
                .build());

        // 1. Blank comment rejected (400)
        AddCommentRequest blankReq = AddCommentRequest.builder().text("   ").build();
        mockMvc.perform(post("/api/media/" + post.getId() + "/comments")
                        .header("Authorization", "Bearer " + viewerToken)
                        .contentType(org.springframework.http.MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(blankReq)))
                .andExpect(status().isBadRequest());

        // 2. Valid comment added by viewer
        AddCommentRequest validReq = AddCommentRequest.builder().text("Awesome picture!").build();
        String respJson = mockMvc.perform(post("/api/media/" + post.getId() + "/comments")
                        .header("Authorization", "Bearer " + viewerToken)
                        .contentType(org.springframework.http.MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(validReq)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.text", is("Awesome picture!")))
                .andExpect(jsonPath("$.user.id", is(viewer.getId().intValue())))
                .andReturn().getResponse().getContentAsString();

        Long commentId = objectMapper.readTree(respJson).get("id").asLong();

        // 3. List comments oldest first
        mockMvc.perform(get("/api/media/" + post.getId() + "/comments")
                        .header("Authorization", "Bearer " + viewerToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items", hasSize(1)))
                .andExpect(jsonPath("$.items[0].id", is(commentId.intValue())));

        // 4. Delete comment by media owner -> 204
        mockMvc.perform(delete("/api/comments/" + commentId)
                        .header("Authorization", "Bearer " + ownerToken))
                .andExpect(status().isNoContent());

        assertFalse(commentRepository.existsById(commentId));
    }
}
