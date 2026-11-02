package com.socialapp.service;

import com.socialapp.entity.Media;
import com.socialapp.entity.enums.MediaType;
import com.socialapp.repository.*;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
public class ScheduledTasksService {

    private final MediaRepository mediaRepository;
    private final MediaTagRepository mediaTagRepository;
    private final LikeRepository likeRepository;
    private final CommentRepository commentRepository;
    private final ShareRepository shareRepository;
    private final StoryViewRepository storyViewRepository;
    private final MediaViewRepository mediaViewRepository;
    private final UserInterestRepository userInterestRepository;
    private final StorageService storageService;

    /**
     * Cleans up expired stories every 10 minutes.
     */
    @Scheduled(fixedRate = 600000)
    @Transactional
    public void cleanupExpiredStories() {
        Instant now = Instant.now();
        List<Media> expiredStories = mediaRepository.findByTypeAndExpiresAtBefore(MediaType.STORY, now);
        if (expiredStories.isEmpty()) {
            return;
        }

        log.info("Found {} expired stories for scheduled cleanup", expiredStories.size());
        for (Media story : expiredStories) {
            try {
                storageService.delete(story.getR2Key());
                if (story.getThumbnailKey() != null && !story.getThumbnailKey().equals(story.getR2Key())) {
                    storageService.delete(story.getThumbnailKey());
                }
            } catch (Exception ex) {
                log.warn("Failed to delete storage asset for expired story {}: {}", story.getId(), ex.getMessage());
            }

            mediaTagRepository.deleteByMediaId(story.getId());
            likeRepository.deleteByMediaId(story.getId());
            commentRepository.deleteByMediaId(story.getId());
            shareRepository.deleteByMediaId(story.getId());
            storyViewRepository.deleteByMediaId(story.getId());
            mediaViewRepository.deleteByMediaId(story.getId());
            mediaRepository.delete(story);
        }
    }

    /**
     * User tag interest decay runs daily at 03:00.
     * Multiplies scores by 0.95 and prunes scores whose absolute value is < 0.5.
     */
    @Scheduled(cron = "0 0 3 * * *")
    @Transactional
    public void decayUserInterests() {
        log.info("Running daily user tag interest decay task");
        int decayed = userInterestRepository.decayAllScores(0.95, Instant.now());
        int pruned = userInterestRepository.pruneLowScores();
        log.info("Decayed {} interest scores, pruned {} low-score entries", decayed, pruned);
    }

    /**
     * Media view log pruning runs weekly on Sunday at midnight.
     * Deletes media views older than 90 days.
     */
    @Scheduled(cron = "0 0 0 * * SUN")
    @Transactional
    public void pruneMediaViews() {
        Instant cutoff = Instant.now().minus(90, ChronoUnit.DAYS);
        log.info("Running weekly media view log pruning before {}", cutoff);
        int deleted = mediaViewRepository.deleteByViewedAtBefore(cutoff);
        log.info("Pruned {} old media view entries", deleted);
    }
}
