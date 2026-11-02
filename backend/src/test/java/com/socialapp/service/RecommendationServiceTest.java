package com.socialapp.service;

import com.socialapp.dto.common.PagedResponse;
import com.socialapp.dto.upload.MediaCardDto;
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
import java.util.*;

import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest
@TestPropertySource(locations = "classpath:application-test.properties")
class RecommendationServiceTest {

    @Autowired
    private RecommendationService recommendationService;

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

    private User testUser;
    private User creatorA;
    private User creatorB;

    @BeforeEach
    void setUp() {
        mediaViewRepository.deleteAll();
        userInterestRepository.deleteAll();
        mediaTagRepository.deleteAll();
        mediaRepository.deleteAll();
        userRepository.deleteAll();

        testUser = userRepository.save(User.builder()
                .username("rec_user")
                .email("rec@test.com")
                .passwordHash("hash")
                .isPrivate(false)
                .build());

        creatorA = userRepository.save(User.builder()
                .username("creator_a")
                .email("ca@test.com")
                .passwordHash("hash")
                .isPrivate(false)
                .build());

        creatorB = userRepository.save(User.builder()
                .username("creator_b")
                .email("cb@test.com")
                .passwordHash("hash")
                .isPrivate(false)
                .build());
    }

    @Test
    @DisplayName("RecommendationService - Cold start user (< 10 views) receives candidate recommendations")
    void testColdStartRecommendations() {
        // Create 4 reels
        for (int i = 1; i <= 4; i++) {
            Media reel = mediaRepository.save(Media.builder()
                    .userId(i % 2 == 0 ? creatorA.getId() : creatorB.getId())
                    .type(MediaType.REEL)
                    .mediaKind(MediaKind.VIDEO)
                    .r2Key("REEL/" + i + ".mp4")
                    .caption("Reel " + i + " #fun" + i)
                    .createdAt(Instant.now().minus(i, ChronoUnit.HOURS))
                    .build());
            mediaTagRepository.save(new MediaTag(reel.getId(), "fun" + i));
        }

        // testUser has 0 views (< 10), so cold start applies
        assertEquals(0, mediaViewRepository.countByUserId(testUser.getId()));

        PagedResponse<MediaCardDto> response = recommendationService.getRecommendedReels(testUser.getId(), 3, Collections.emptySet());
        assertNotNull(response);
        assertEquals(3, response.getItems().size());

        // Check for no duplicates
        Set<Long> ids = new HashSet<>();
        for (MediaCardDto item : response.getItems()) {
            assertTrue(ids.add(item.getId()), "Returned items should have no duplicates");
        }
    }

    @Test
    @DisplayName("RecommendationService - High interest score elevates reels with matching tags")
    void testInterestScoreElevatesMatchingReels() {
        Media reelGym = mediaRepository.save(Media.builder()
                .userId(creatorA.getId())
                .type(MediaType.REEL)
                .mediaKind(MediaKind.VIDEO)
                .r2Key("REEL/gym.mp4")
                .caption("Workout daily #fitness")
                .createdAt(Instant.now().minus(1, ChronoUnit.HOURS))
                .build());
        mediaTagRepository.save(new MediaTag(reelGym.getId(), "fitness"));

        Media reelCooking = mediaRepository.save(Media.builder()
                .userId(creatorB.getId())
                .type(MediaType.REEL)
                .mediaKind(MediaKind.VIDEO)
                .r2Key("REEL/cook.mp4")
                .caption("Baking bread #cooking")
                .createdAt(Instant.now().minus(2, ChronoUnit.HOURS))
                .build());
        mediaTagRepository.save(new MediaTag(reelCooking.getId(), "cooking"));

        // Simulate 12 views so user is NOT cold
        for (int i = 0; i < 12; i++) {
            mediaViewRepository.save(MediaView.builder()
                    .userId(testUser.getId())
                    .mediaId(reelCooking.getId())
                    .watchMs(3000)
                    .durationMs(5000)
                    .completed(false)
                    .viewedAt(Instant.now().minus(10, ChronoUnit.DAYS))
                    .build());
        }

        // Give high score on fitness
        recommendationService.updateInterestForMedia(testUser.getId(), reelGym.getId(), 20.0);

        PagedResponse<MediaCardDto> response = recommendationService.getRecommendedReels(testUser.getId(), 2, Collections.emptySet());
        assertNotNull(response);
        assertFalse(response.getItems().isEmpty());
        // Gym reel should be ranked first due to high personalized score
        assertEquals(reelGym.getId(), response.getItems().get(0).getId());
    }

    @Test
    @DisplayName("RecommendationService - Exclude list is strictly respected")
    void testExcludeListRespected() {
        Media r1 = mediaRepository.save(Media.builder()
                .userId(creatorA.getId())
                .type(MediaType.REEL)
                .mediaKind(MediaKind.VIDEO)
                .r2Key("REEL/r1.mp4")
                .caption("Reel 1")
                .build());

        Media r2 = mediaRepository.save(Media.builder()
                .userId(creatorB.getId())
                .type(MediaType.REEL)
                .mediaKind(MediaKind.VIDEO)
                .r2Key("REEL/r2.mp4")
                .caption("Reel 2")
                .build());

        PagedResponse<MediaCardDto> response = recommendationService.getRecommendedReels(testUser.getId(), 5, Set.of(r1.getId()));
        assertEquals(1, response.getItems().size());
        assertEquals(r2.getId(), response.getItems().get(0).getId());
    }
}
