package com.socialapp.upload;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.socialapp.dto.upload.ConfirmUploadRequest;
import com.socialapp.dto.upload.PresignRequest;
import com.socialapp.entity.MediaTag;
import com.socialapp.entity.User;
import com.socialapp.entity.enums.MediaType;
import com.socialapp.entity.enums.UploadType;
import com.socialapp.repository.UserRepository;
import com.socialapp.security.JwtTokenProvider;
import com.socialapp.service.StorageService;
import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
@TestPropertySource(locations = "classpath:application-test.properties")
class UploadControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private JwtTokenProvider jwtTokenProvider;

    @Autowired
    private StorageService storageService;

    @Autowired
    private EntityManager entityManager;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    private User testUser1;
    private User testUser2;
    private String token1;
    private String token2;

    @BeforeEach
    void setUp() {
        jdbcTemplate.execute("DELETE FROM media_views");
        jdbcTemplate.execute("DELETE FROM story_views");
        jdbcTemplate.execute("DELETE FROM likes");
        jdbcTemplate.execute("DELETE FROM comments");
        jdbcTemplate.execute("DELETE FROM shares");
        jdbcTemplate.execute("DELETE FROM media_tags");
        jdbcTemplate.execute("DELETE FROM media");
        jdbcTemplate.execute("DELETE FROM follows");
        jdbcTemplate.execute("DELETE FROM follow_requests");
        jdbcTemplate.execute("DELETE FROM user_interests");
        jdbcTemplate.execute("DELETE FROM users");

        testUser1 = userRepository.save(User.builder()
                .username("alice_test")
                .email("alice@test.com")
                .passwordHash("hashedpass")
                .bio("Photographer")
                .avatarKey("AVATAR/1/alice.jpg")
                .isPrivate(false)
                .notificationsEnabled(true)
                .build());

        testUser2 = userRepository.save(User.builder()
                .username("bob_test")
                .email("bob@test.com")
                .passwordHash("hashedpass")
                .bio("Developer")
                .avatarKey("AVATAR/2/bob.jpg")
                .isPrivate(false)
                .notificationsEnabled(true)
                .build());

        token1 = jwtTokenProvider.generateToken(testUser1.getId(), testUser1.getUsername());
        token2 = jwtTokenProvider.generateToken(testUser2.getId(), testUser2.getUsername());
    }

    @Test
    @DisplayName("POST /api/uploads/presign - Valid image request returns 200 with uploadUrl and r2Key")
    void testPresignValidImage() throws Exception {
        PresignRequest request = PresignRequest.builder()
                .fileName("holiday.jpg")
                .contentType("image/jpeg")
                .type(UploadType.POST)
                .fileSize(2048576L)
                .build();

        mockMvc.perform(post("/api/uploads/presign")
                        .header("Authorization", "Bearer " + token1)
                        .contentType(org.springframework.http.MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.uploadUrl").isNotEmpty())
                .andExpect(jsonPath("$.r2Key").value(startsWith("POST/" + testUser1.getId() + "/")))
                .andExpect(jsonPath("$.r2Key").value(endsWith("holiday.jpg")));
    }

    @Test
    @DisplayName("POST /api/uploads/presign - Valid video request returns 200 with uploadUrl and r2Key")
    void testPresignValidVideo() throws Exception {
        PresignRequest request = PresignRequest.builder()
                .fileName("dance.mp4")
                .contentType("video/mp4")
                .type(UploadType.REEL)
                .fileSize(15000000L)
                .build();

        mockMvc.perform(post("/api/uploads/presign")
                        .header("Authorization", "Bearer " + token1)
                        .contentType(org.springframework.http.MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.uploadUrl").isNotEmpty())
                .andExpect(jsonPath("$.r2Key").value(startsWith("REEL/" + testUser1.getId() + "/")))
                .andExpect(jsonPath("$.r2Key").value(endsWith("dance.mp4")));
    }

    @Test
    @DisplayName("POST /api/uploads/presign - Unsupported contentType returns 400 Bad Request")
    void testPresignUnsupportedContentType() throws Exception {
        PresignRequest request = PresignRequest.builder()
                .fileName("document.pdf")
                .contentType("application/pdf")
                .type(UploadType.POST)
                .fileSize(500000L)
                .build();

        mockMvc.perform(post("/api/uploads/presign")
                        .header("Authorization", "Bearer " + token1)
                        .contentType(org.springframework.http.MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.status").value(400))
                .andExpect(jsonPath("$.message").value(containsString("Unsupported content type")));
    }

    @Test
    @DisplayName("POST /api/uploads/presign - Oversized image (>10MB) returns 400 Bad Request")
    void testPresignOversizedImage() throws Exception {
        PresignRequest request = PresignRequest.builder()
                .fileName("huge.png")
                .contentType("image/png")
                .type(UploadType.POST)
                .fileSize(12L * 1024 * 1024)
                .build();

        mockMvc.perform(post("/api/uploads/presign")
                        .header("Authorization", "Bearer " + token1)
                        .contentType(org.springframework.http.MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.status").value(400))
                .andExpect(jsonPath("$.message").value(containsString("Image file size cannot exceed 10MB")));
    }

    @Test
    @DisplayName("POST /api/uploads/presign - Oversized video (>100MB) returns 400 Bad Request")
    void testPresignOversizedVideo() throws Exception {
        PresignRequest request = PresignRequest.builder()
                .fileName("giant_film.mp4")
                .contentType("video/mp4")
                .type(UploadType.REEL)
                .fileSize(120L * 1024 * 1024)
                .build();

        mockMvc.perform(post("/api/uploads/presign")
                        .header("Authorization", "Bearer " + token1)
                        .contentType(org.springframework.http.MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.status").value(400))
                .andExpect(jsonPath("$.message").value(containsString("Video file size cannot exceed 100MB")));
    }

    @Test
    @DisplayName("POST /api/uploads/presign - REEL with non-mp4 contentType returns 400 Bad Request")
    void testPresignReelMustBeVideo() throws Exception {
        PresignRequest request = PresignRequest.builder()
                .fileName("image.jpg")
                .contentType("image/jpeg")
                .type(UploadType.REEL)
                .fileSize(1000000L)
                .build();

        mockMvc.perform(post("/api/uploads/presign")
                        .header("Authorization", "Bearer " + token1)
                        .contentType(org.springframework.http.MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value(containsString("REEL must be video/mp4")));
    }

    @Test
    @DisplayName("POST /api/uploads/presign - AVATAR with video contentType returns 400 Bad Request")
    void testPresignAvatarMustBeImage() throws Exception {
        PresignRequest request = PresignRequest.builder()
                .fileName("avatar.mp4")
                .contentType("video/mp4")
                .type(UploadType.AVATAR)
                .fileSize(2000000L)
                .build();

        mockMvc.perform(post("/api/uploads/presign")
                        .header("Authorization", "Bearer " + token1)
                        .contentType(org.springframework.http.MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value(containsString("AVATAR must be an image")));
    }

    @Test
    @DisplayName("POST /api/uploads/presign - Unauthenticated request returns 401 Unauthorized")
    void testPresignUnauthenticated() throws Exception {
        PresignRequest request = PresignRequest.builder()
                .fileName("photo.jpg")
                .contentType("image/jpeg")
                .type(UploadType.POST)
                .fileSize(500000L)
                .build();

        mockMvc.perform(post("/api/uploads/presign")
                        .contentType(org.springframework.http.MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isUnauthorized());
    }

    @Test
    @DisplayName("PUT & GET /api/uploads/local-storage/** - Upload and stream back binary file")
    void testLocalStoragePutAndGet() throws Exception {
        String key = "POST/" + testUser1.getId() + "/upload-stream.jpg";
        byte[] payload = "sample-image-data-payload-bytes".getBytes(StandardCharsets.UTF_8);

        // 1. PUT upload
        mockMvc.perform(put("/api/uploads/local-storage/" + key)
                        .contentType(org.springframework.http.MediaType.IMAGE_JPEG)
                        .content(payload))
                .andExpect(status().isOk());

        assertThat(storageService.exists(key)).isTrue();

        // 2. GET download
        mockMvc.perform(get("/api/uploads/local-storage/" + key))
                .andExpect(status().isOk())
                .andExpect(header().string("Content-Type", startsWith("image/jpeg")))
                .andExpect(content().bytes(payload));
    }

    @Test
    @DisplayName("GET /api/uploads/local-storage/** - Non-existent file returns 404 Not Found")
    void testLocalStorageGetMissing() throws Exception {
        mockMvc.perform(get("/api/uploads/local-storage/MISSING/file.jpg"))
                .andExpect(status().isNotFound());
    }

    @Test
    @DisplayName("POST /api/uploads/confirm - Successful confirmation creates Media row and tags")
    @Transactional
    void testConfirmUploadSuccess() throws Exception {
        String key = "POST/" + testUser1.getId() + "/nature.jpg";
        byte[] payload = "image-data".getBytes(StandardCharsets.UTF_8);
        storageService.upload(key, payload, "image/jpeg");

        ConfirmUploadRequest request = ConfirmUploadRequest.builder()
                .r2Key(key)
                .type(MediaType.POST)
                .caption("Exploring the Swiss Alps! #mountains #travel #hiking")
                .build();

        mockMvc.perform(post("/api/uploads/confirm")
                        .header("Authorization", "Bearer " + token1)
                        .contentType(org.springframework.http.MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.id").isNumber())
                .andExpect(jsonPath("$.type").value("POST"))
                .andExpect(jsonPath("$.mediaKind").value("IMAGE"))
                .andExpect(jsonPath("$.caption").value("Exploring the Swiss Alps! #mountains #travel #hiking"))
                .andExpect(jsonPath("$.tags", containsInAnyOrder("mountains", "travel", "hiking")))
                .andExpect(jsonPath("$.mediaUrl").isNotEmpty())
                .andExpect(jsonPath("$.thumbnailUrl").isNotEmpty())
                .andExpect(jsonPath("$.user.id").value(testUser1.getId()))
                .andExpect(jsonPath("$.user.username").value("alice_test"));

        // Verify tags persisted in DB
        List<MediaTag> dbTags = entityManager.createQuery("SELECT t FROM MediaTag t", MediaTag.class).getResultList();
        assertThat(dbTags).extracting(MediaTag::getTag).contains("mountains", "travel", "hiking");
    }

    @Test
    @DisplayName("POST /api/uploads/confirm - Key prefix mismatch returns 403 Forbidden")
    void testConfirmKeyPrefixMismatch() throws Exception {
        // User 1 uploads a file
        String key = "POST/" + testUser1.getId() + "/secret.jpg";
        storageService.upload(key, "data".getBytes(StandardCharsets.UTF_8), "image/jpeg");

        // User 2 attempts to confirm User 1's key
        ConfirmUploadRequest request = ConfirmUploadRequest.builder()
                .r2Key(key)
                .type(MediaType.POST)
                .caption("Hacked caption")
                .build();

        mockMvc.perform(post("/api/uploads/confirm")
                        .header("Authorization", "Bearer " + token2)
                        .contentType(org.springframework.http.MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.status").value(403))
                .andExpect(jsonPath("$.message").value(containsString("key prefix does not match")));
    }

    @Test
    @DisplayName("POST /api/uploads/confirm - Missing file in storage returns 404 Not Found")
    void testConfirmMissingFileThrows404() throws Exception {
        String key = "POST/" + testUser1.getId() + "/phantom.jpg";
        storageService.delete(key);

        ConfirmUploadRequest request = ConfirmUploadRequest.builder()
                .r2Key(key)
                .type(MediaType.POST)
                .caption("Never uploaded")
                .build();

        mockMvc.perform(post("/api/uploads/confirm")
                        .header("Authorization", "Bearer " + token1)
                        .contentType(org.springframework.http.MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.status").value(404));
    }
}
