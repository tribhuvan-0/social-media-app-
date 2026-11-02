package com.socialapp.storage;

import com.socialapp.entity.Media;
import com.socialapp.entity.User;
import com.socialapp.entity.enums.MediaKind;
import com.socialapp.entity.enums.MediaType;
import com.socialapp.repository.UserRepository;
import com.socialapp.service.FfmpegThumbnailService;
import com.socialapp.service.StorageService;
import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.TestPropertySource;
import org.springframework.transaction.support.TransactionTemplate;

import java.io.InputStream;
import java.time.Instant;
import java.util.concurrent.CompletableFuture;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;

@SpringBootTest
@TestPropertySource(locations = "classpath:application-test.properties")
class FfmpegThumbnailServiceTest {

    @Autowired
    private FfmpegThumbnailService ffmpegThumbnailService;

    @Autowired
    private StorageService storageService;

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private EntityManager entityManager;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Autowired
    private TransactionTemplate transactionTemplate;

    private User user;

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

        user = userRepository.save(User.builder()
                .username("videomaker")
                .email("video@test.com")
                .passwordHash("hashed")
                .bio("Creator")
                .avatarKey("AVATAR/1/video.jpg")
                .build());
    }

    @Test
    @DisplayName("FFmpeg generates valid JPEG thumbnail from real MP4 video and updates Media entity")
    void testRealFfmpegThumbnailExtraction() throws Exception {
        byte[] videoBytes;
        try (InputStream in = getClass().getResourceAsStream("/sample_tiny.mp4")) {
            assertThat(in).isNotNull();
            videoBytes = in.readAllBytes();
        }

        String videoKey = "REEL/" + user.getId() + "/sample.mp4";
        storageService.upload(videoKey, videoBytes, "video/mp4");

        Long mediaId = transactionTemplate.execute(status -> {
            Media media = Media.builder()
                    .userId(user.getId())
                    .type(MediaType.REEL)
                    .mediaKind(MediaKind.VIDEO)
                    .r2Key(videoKey)
                    .thumbnailKey(null)
                    .caption("Sample video #reel")
                    .createdAt(Instant.now())
                    .build();
            entityManager.persist(media);
            entityManager.flush();
            return media.getId();
        });

        assertThat(mediaId).isNotNull();

        // Run thumbnail generation
        CompletableFuture<Void> future = ffmpegThumbnailService.generateThumbnailAsync(mediaId, videoKey, user.getId());
        future.join();

        // Refresh media from DB
        Media updated = transactionTemplate.execute(status -> entityManager.find(Media.class, mediaId));
        assertThat(updated).isNotNull();
        assertThat(updated.getThumbnailKey()).isNotNull();
        assertThat(updated.getThumbnailKey()).startsWith("thumbnails/" + user.getId() + "/");
        assertThat(updated.getThumbnailKey()).endsWith(".jpg");

        // Verify thumbnail file physically exists in storage and has valid JPEG header
        assertThat(storageService.exists(updated.getThumbnailKey())).isTrue();
        assertThat(storageService.getContentLength(updated.getThumbnailKey())).isGreaterThan(0);

        try (InputStream thumbIn = storageService.download(updated.getThumbnailKey())) {
            byte[] thumbBytes = thumbIn.readAllBytes();
            assertThat(thumbBytes.length).isGreaterThan(10);
            // JPEG magic bytes: 0xFF, 0xD8
            assertThat(thumbBytes[0]).isEqualTo((byte) 0xFF);
            assertThat(thumbBytes[1]).isEqualTo((byte) 0xD8);
        }
    }

    @Test
    @DisplayName("FFmpeg robust fallback: non-existent video does not crash or throw unhandled exception")
    void testFfmpegFallbackOnMissingFile() {
        assertThatCode(() -> {
            CompletableFuture<Void> future = ffmpegThumbnailService.generateThumbnailAsync(999999L, "MISSING/video.mp4", 1L);
            future.join();
        }).doesNotThrowAnyException();
    }
}
