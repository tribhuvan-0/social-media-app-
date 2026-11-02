package com.socialapp.service;

import com.socialapp.entity.*;
import com.socialapp.entity.enums.MediaKind;
import com.socialapp.entity.enums.MediaType;
import com.socialapp.repository.*;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.TestPropertySource;

import java.time.Instant;
import java.time.temporal.ChronoUnit;

import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest
@TestPropertySource(locations = "classpath:application-test.properties")
class ScheduledTasksServiceTest {

    @Autowired
    private ScheduledTasksService scheduledTasksService;

    @Autowired
    private MediaRepository mediaRepository;

    @Autowired
    private UserInterestRepository userInterestRepository;

    @Autowired
    private MediaViewRepository mediaViewRepository;

    @Autowired
    private UserRepository userRepository;

    private User testUser;

    @BeforeEach
    void setUp() {
        mediaViewRepository.deleteAll();
        userInterestRepository.deleteAll();
        mediaRepository.deleteAll();
        userRepository.deleteAll();

        testUser = userRepository.save(User.builder()
                .username("sched_user")
                .email("sched@test.com")
                .passwordHash("hash")
                .build());
    }

    @Test
    @DisplayName("ScheduledTasksService - Expired story cleanup deletes only expired stories")
    void testCleanupExpiredStories() {
        Instant now = Instant.now();

        Media expired = mediaRepository.save(Media.builder()
                .userId(testUser.getId())
                .type(MediaType.STORY)
                .mediaKind(MediaKind.IMAGE)
                .r2Key("STORY/" + testUser.getId() + "/exp.jpg")
                .expiresAt(now.minus(1, ChronoUnit.HOURS))
                .build());

        Media active = mediaRepository.save(Media.builder()
                .userId(testUser.getId())
                .type(MediaType.STORY)
                .mediaKind(MediaKind.IMAGE)
                .r2Key("STORY/" + testUser.getId() + "/act.jpg")
                .expiresAt(now.plus(10, ChronoUnit.HOURS))
                .build());

        scheduledTasksService.cleanupExpiredStories();

        assertFalse(mediaRepository.existsById(expired.getId()));
        assertTrue(mediaRepository.existsById(active.getId()));
    }

    @Test
    @DisplayName("ScheduledTasksService - User interest decay multiplies by 0.95 and prunes abs(score) < 0.5")
    void testDecayUserInterests() {
        // High score: 10.0 * 0.95 = 9.5 (survives)
        userInterestRepository.save(UserInterest.builder()
                .userId(testUser.getId())
                .tag("fitness")
                .score(10.0)
                .updatedAt(Instant.now())
                .build());

        // Low score: 0.4 (should be pruned after decay because < 0.5)
        userInterestRepository.save(UserInterest.builder()
                .userId(testUser.getId())
                .tag("cooking")
                .score(0.4)
                .updatedAt(Instant.now())
                .build());

        scheduledTasksService.decayUserInterests();

        UserInterest fitness = userInterestRepository.findByUserIdAndTag(testUser.getId(), "fitness").orElse(null);
        assertNotNull(fitness);
        assertEquals(9.5, fitness.getScore(), 0.01);

        UserInterest cooking = userInterestRepository.findByUserIdAndTag(testUser.getId(), "cooking").orElse(null);
        assertNull(cooking);
    }

    @Test
    @DisplayName("ScheduledTasksService - Pruning media views older than 90 days")
    void testPruneMediaViews() {
        Media reel = mediaRepository.save(Media.builder()
                .userId(testUser.getId())
                .type(MediaType.REEL)
                .mediaKind(MediaKind.VIDEO)
                .r2Key("REEL/" + testUser.getId() + "/r.mp4")
                .build());

        Instant now = Instant.now();

        MediaView oldView = mediaViewRepository.save(MediaView.builder()
                .userId(testUser.getId())
                .mediaId(reel.getId())
                .watchMs(5000L)
                .durationMs(5000L)
                .completed(true)
                .viewedAt(now.minus(95, ChronoUnit.DAYS))
                .build());

        MediaView recentView = mediaViewRepository.save(MediaView.builder()
                .userId(testUser.getId())
                .mediaId(reel.getId())
                .watchMs(5000L)
                .durationMs(5000L)
                .completed(true)
                .viewedAt(now.minus(10, ChronoUnit.DAYS))
                .build());

        scheduledTasksService.pruneMediaViews();

        assertFalse(mediaViewRepository.existsById(oldView.getId()));
        assertTrue(mediaViewRepository.existsById(recentView.getId()));
    }
}
