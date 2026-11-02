package com.socialapp.service;

import com.socialapp.config.RecommendationProperties;
import com.socialapp.dto.common.PagedResponse;
import com.socialapp.dto.upload.MediaCardDto;
import com.socialapp.entity.Media;
import com.socialapp.entity.MediaTag;
import com.socialapp.entity.UserInterest;
import com.socialapp.entity.enums.MediaType;
import com.socialapp.exception.BadRequestException;
import com.socialapp.mapper.MediaMapper;
import com.socialapp.repository.MediaRepository;
import com.socialapp.repository.MediaTagRepository;
import com.socialapp.repository.MediaViewRepository;
import com.socialapp.repository.UserInterestRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.*;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class RecommendationService {

    private final RecommendationProperties properties;
    private final MediaRepository mediaRepository;
    private final MediaTagRepository mediaTagRepository;
    private final MediaViewRepository mediaViewRepository;
    private final UserInterestRepository userInterestRepository;
    private final MediaMapper mediaMapper;

    @Transactional
    public void updateInterestForMedia(Long userId, Long mediaId, double delta) {
        List<MediaTag> tags = mediaTagRepository.findByMediaId(mediaId);
        if (tags.isEmpty()) {
            return;
        }

        Instant now = Instant.now();
        for (MediaTag mediaTag : tags) {
            String tag = mediaTag.getTag();
            UserInterest interest = userInterestRepository.findByUserIdAndTag(userId, tag)
                    .orElseGet(() -> UserInterest.builder()
                            .userId(userId)
                            .tag(tag)
                            .score(0.0)
                            .updatedAt(now)
                            .build());

            double newScore = Math.min(properties.getScoreMax(), Math.max(properties.getScoreMin(), interest.getScore() + delta));
            interest.setScore(newScore);
            interest.setUpdatedAt(now);
            userInterestRepository.save(interest);
        }
    }

    @Transactional
    public void updateInterestOnFollow(Long userId, Long creatorId) {
        List<Media> creatorReels = mediaRepository.findByUserIdAndType(creatorId, MediaType.REEL);
        if (creatorReels.isEmpty()) {
            return;
        }

        List<Long> reelIds = creatorReels.stream().map(Media::getId).toList();
        List<String> topTags = mediaTagRepository.findTopTagsInMediaIds(reelIds, PageRequest.of(0, 3));
        if (topTags.isEmpty()) {
            return;
        }

        Instant now = Instant.now();
        double delta = properties.getFollowCreatorWeight();
        for (String tag : topTags) {
            UserInterest interest = userInterestRepository.findByUserIdAndTag(userId, tag)
                    .orElseGet(() -> UserInterest.builder()
                            .userId(userId)
                            .tag(tag)
                            .score(0.0)
                            .updatedAt(now)
                            .build());

            double newScore = Math.min(properties.getScoreMax(), Math.max(properties.getScoreMin(), interest.getScore() + delta));
            interest.setScore(newScore);
            interest.setUpdatedAt(now);
            userInterestRepository.save(interest);
        }
    }

    @Transactional(readOnly = true)
    public PagedResponse<MediaCardDto> getRecommendedReels(Long currentUserId, int size, Set<Long> excludeIds) {
        if (size <= 0 || size > 20) {
            throw new BadRequestException("Reels request size must be between 1 and 20");
        }

        Set<Long> excluded = (excludeIds != null) ? new HashSet<>(excludeIds) : new HashSet<>();

        // Cold user check: user has fewer than 10 rows in media_views
        long viewCount = mediaViewRepository.countByUserId(currentUserId);
        boolean isCold = viewCount < properties.getColdStartThreshold();

        Instant now = Instant.now();
        Instant sevenDaysAgo = now.minus(7, ChronoUnit.DAYS);
        Instant ninetyDaysAgo = now.minus(90, ChronoUnit.DAYS);

        // Fetch candidate reels: REEL, not mine, owner not private unless followed
        List<Media> allCandidates = mediaRepository.findReelCandidatesForUser(currentUserId);

        // Filter out excluded reels
        List<Media> eligibleCandidates = allCandidates.stream()
                .filter(m -> !excluded.contains(m.getId()))
                .toList();

        if (eligibleCandidates.isEmpty()) {
            return PagedResponse.of(Collections.emptyList(), false);
        }

        // Fetch user views history for loopback
        Set<Long> viewedLast7Days = new HashSet<>(mediaViewRepository.findViewedMediaIdsSince(currentUserId, sevenDaysAgo));

        // Unseen in last 7 days + created within 90 days
        List<Media> freshCandidates = eligibleCandidates.stream()
                .filter(m -> !viewedLast7Days.contains(m.getId()))
                .filter(m -> m.getCreatedAt() != null && m.getCreatedAt().isAfter(ninetyDaysAgo))
                .toList();

        // Fallback 1: relax 90 days rule if fresh candidates are fewer than size
        if (freshCandidates.size() < size) {
            freshCandidates = eligibleCandidates.stream()
                    .filter(m -> !viewedLast7Days.contains(m.getId()))
                    .toList();
        }

        // Fallback 2: Catalog loopback: if candidates exhaust, allow reels seen > 7 days ago or all eligible
        List<Media> activeCandidatePool = new ArrayList<>(freshCandidates);
        List<Media> loopbackPool = eligibleCandidates.stream()
                .filter(m -> !activeCandidatePool.contains(m))
                .toList();

        // Batch load tags for all eligible candidates
        List<Long> eligibleMediaIds = eligibleCandidates.stream().map(Media::getId).toList();
        Map<Long, Set<String>> mediaTagMap = new HashMap<>();
        if (!eligibleMediaIds.isEmpty()) {
            List<MediaTag> tags = mediaTagRepository.findByMediaIdIn(eligibleMediaIds);
            for (MediaTag t : tags) {
                mediaTagMap.computeIfAbsent(t.getMediaId(), k -> new HashSet<>()).add(t.getTag());
            }
        }

        // Fetch user interests
        List<UserInterest> userInterests = userInterestRepository.findByUserId(currentUserId);
        Map<String, Double> interestScoreMap = userInterests.stream()
                .collect(Collectors.toMap(UserInterest::getTag, UserInterest::getScore, (s1, s2) -> s1));

        Set<String> top10UserTags = userInterests.stream()
                .sorted(Comparator.comparingDouble(UserInterest::getScore).reversed())
                .limit(10)
                .map(UserInterest::getTag)
                .collect(Collectors.toSet());

        // Build 3 Pools from active candidate pool
        List<Media> personalizedPool = new ArrayList<>();
        List<Media> explorationPool = new ArrayList<>();
        List<Media> popularPool = new ArrayList<>();

        Map<Long, Double> personalizedScores = new HashMap<>();
        Map<Long, Double> popularScores = new HashMap<>();

        for (Media reel : activeCandidatePool) {
            Set<String> reelTags = mediaTagMap.getOrDefault(reel.getId(), Collections.emptySet());

            // 1. Personalized check: has at least one tag where my score > 0
            double tagScoreSum = 0.0;
            boolean hasPositiveTag = false;
            for (String tag : reelTags) {
                double score = interestScoreMap.getOrDefault(tag, 0.0);
                if (score > 0.0) {
                    hasPositiveTag = true;
                    tagScoreSum += score;
                }
            }

            if (hasPositiveTag) {
                double ageDays = Math.max(0.0, ChronoUnit.HOURS.between(reel.getCreatedAt(), now) / 24.0);
                double recencyFactor = 1.0 / (1.0 + ageDays / 7.0);
                long engagement = reel.getLikeCount() * 3L + reel.getCommentCount() * 4L + reel.getShareCount() * 5L + reel.getViewCount();
                double engagementFactor = 1.0 + Math.log10(1.0 + engagement);
                double pScore = tagScoreSum * recencyFactor * engagementFactor;
                personalizedScores.put(reel.getId(), pScore);
                personalizedPool.add(reel);
            }

            // 2. Exploration check: tags do not overlap top 10 tags (untagged reels count as exploration)
            boolean overlapsTop10 = reelTags.stream().anyMatch(top10UserTags::contains);
            if (!overlapsTop10) {
                explorationPool.add(reel);
            }

            // 3. Popular pool: popular score
            double ageHours = Math.max(0.0, ChronoUnit.MINUTES.between(reel.getCreatedAt(), now) / 60.0);
            long popEngagement = reel.getLikeCount() * 3L + reel.getCommentCount() * 4L + reel.getShareCount() * 5L + reel.getViewCount();
            double popScore = popEngagement / Math.pow(ageHours + 2.0, 1.2);
            popularScores.put(reel.getId(), popScore);
            popularPool.add(reel);
        }

        // Sort personalized by score descending
        personalizedPool.sort((m1, m2) -> Double.compare(personalizedScores.getOrDefault(m2.getId(), 0.0), personalizedScores.getOrDefault(m1.getId(), 0.0)));
        // Shuffle exploration for randomness
        Collections.shuffle(explorationPool);
        // Sort popular by score descending
        popularPool.sort((m1, m2) -> Double.compare(popularScores.getOrDefault(m2.getId(), 0.0), popularScores.getOrDefault(m1.getId(), 0.0)));

        // Calculate quotas
        int quotaPersonalized;
        int quotaExploration;
        int quotaPopular;

        if (isCold) {
            // Cold start: 80% Exploration, 20% Popular
            quotaExploration = (int) Math.round(size * properties.getColdExplorationRatio());
            quotaPopular = size - quotaExploration;
            quotaPersonalized = 0;
        } else {
            // Normal: 40% Personalized, 30% Exploration, 30% Popular
            quotaPersonalized = (int) Math.round(size * properties.getNormalPersonalizedRatio());
            quotaExploration = (int) Math.round(size * properties.getNormalExplorationRatio());
            quotaPopular = size - quotaPersonalized - quotaExploration;
            if (quotaPopular < 0) {
                quotaPopular = 0;
            }
        }

        LinkedHashSet<Media> selectedReels = new LinkedHashSet<>();

        // Helper to select distinct items from a pool
        selectFromPool(selectedReels, personalizedPool, quotaPersonalized);
        selectFromPool(selectedReels, explorationPool, quotaExploration);
        selectFromPool(selectedReels, popularPool, quotaPopular);

        // If short, fill from remaining pools in order: Personalized -> Exploration -> Popular
        if (selectedReels.size() < size) {
            selectFromPool(selectedReels, personalizedPool, size - selectedReels.size());
        }
        if (selectedReels.size() < size) {
            selectFromPool(selectedReels, explorationPool, size - selectedReels.size());
        }
        if (selectedReels.size() < size) {
            selectFromPool(selectedReels, popularPool, size - selectedReels.size());
        }

        // If still short, loop back to candidate loopbackPool (reels seen > 7 days ago)
        if (selectedReels.size() < size && !loopbackPool.isEmpty()) {
            List<Media> shuffledLoopback = new ArrayList<>(loopbackPool);
            Collections.shuffle(shuffledLoopback);
            selectFromPool(selectedReels, shuffledLoopback, size - selectedReels.size());
        }

        // If still short, draw from any remaining eligible candidates
        if (selectedReels.size() < size) {
            selectFromPool(selectedReels, eligibleCandidates, size - selectedReels.size());
        }

        List<Media> resultList = new ArrayList<>(selectedReels);

        // Creator anti-clumping: Reorder so the same creator never appears twice in a row when avoidable
        applyCreatorAntiClumping(resultList);

        // Determine hasNext: false ONLY when no candidate reels remain at all
        int totalRemainingCandidates = eligibleCandidates.size() - resultList.size();
        boolean hasNext = totalRemainingCandidates > 0;

        List<MediaCardDto> dtoList = mediaMapper.toMediaCardDtoList(resultList, currentUserId);
        return PagedResponse.of(dtoList, hasNext);
    }

    private void selectFromPool(Set<Media> destination, List<Media> sourcePool, int needed) {
        int added = 0;
        for (Media m : sourcePool) {
            if (added >= needed) {
                break;
            }
            if (destination.add(m)) {
                added++;
            }
        }
    }

    /**
     * Reorders candidates so the same creator does not appear in consecutive slots when avoidable.
     */
    private void applyCreatorAntiClumping(List<Media> list) {
        if (list.size() <= 2) {
            return;
        }
        for (int i = 1; i < list.size(); i++) {
            Long prevCreator = list.get(i - 1).getUserId();
            Long currentCreator = list.get(i).getUserId();
            if (Objects.equals(prevCreator, currentCreator)) {
                // Find next item with different creator and swap
                int swapIndex = -1;
                for (int j = i + 1; j < list.size(); j++) {
                    if (!Objects.equals(list.get(j).getUserId(), prevCreator)) {
                        swapIndex = j;
                        break;
                    }
                }
                if (swapIndex != -1) {
                    Media temp = list.get(i);
                    list.set(i, list.get(swapIndex));
                    list.set(swapIndex, temp);
                }
            }
        }
    }
}
