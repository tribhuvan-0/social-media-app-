package com.socialapp.service;

import com.socialapp.dto.media.ItemsResponse;
import com.socialapp.dto.media.StoryGroupDto;
import com.socialapp.dto.media.StoryItemDto;
import com.socialapp.dto.user.UserSummaryDto;
import com.socialapp.entity.Media;
import com.socialapp.entity.StoryView;
import com.socialapp.entity.User;
import com.socialapp.entity.enums.MediaType;
import com.socialapp.exception.NotFoundException;
import com.socialapp.repository.*;
import com.socialapp.util.MediaUrlBuilder;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.*;
import java.util.function.Function;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class StoriesService {

    private final MediaRepository mediaRepository;
    private final StoryViewRepository storyViewRepository;
    private final FollowRepository followRepository;
    private final FollowRequestRepository followRequestRepository;
    private final UserRepository userRepository;
    private final MediaUrlBuilder mediaUrlBuilder;

    @Transactional(readOnly = true)
    public ItemsResponse<StoryGroupDto> getStories(Long currentUserId) {
        Instant now = Instant.now();
        List<Long> followedIds = followRepository.findFollowingIdsByFollowerId(currentUserId);
        Set<Long> userIds = new LinkedHashSet<>();
        userIds.add(currentUserId);
        userIds.addAll(followedIds);

        // Active stories for self and followed users, ordered oldest to newest inside group
        List<Media> activeStories = mediaRepository.findByUserIdInAndTypeAndExpiresAtAfterOrderByCreatedAtAsc(
                userIds,
                MediaType.STORY,
                now
        );

        if (activeStories.isEmpty()) {
            return ItemsResponse.of(Collections.emptyList());
        }

        // Group stories by userId preserving order
        Map<Long, List<Media>> storiesByUser = new LinkedHashMap<>();
        for (Media story : activeStories) {
            storiesByUser.computeIfAbsent(story.getUserId(), k -> new ArrayList<>()).add(story);
        }

        List<Long> allStoryMediaIds = activeStories.stream().map(Media::getId).toList();
        Set<Long> seenMediaIds = new HashSet<>(
                storyViewRepository.findViewedMediaIdsByUserIdAndMediaIdIn(currentUserId, allStoryMediaIds)
        );

        List<Long> authorIds = new ArrayList<>(storiesByUser.keySet());
        Map<Long, User> userMap = userRepository.findAllByIdIn(authorIds).stream()
                .collect(Collectors.toMap(User::getId, Function.identity(), (u1, u2) -> u1));

        Set<Long> followedAuthorIds = new HashSet<>(
                followRepository.findFollowingIdsByFollowerIdAndFollowingIdIn(currentUserId, authorIds)
        );
        Set<Long> requestedAuthorIds = new HashSet<>(
                followRequestRepository.findRequestedTargetIdsByRequesterIdAndTargetIdIn(currentUserId, authorIds)
        );

        List<StoryGroupDto> groups = new ArrayList<>();
        StoryGroupDto myGroup = null;

        for (Map.Entry<Long, List<Media>> entry : storiesByUser.entrySet()) {
            Long authorId = entry.getKey();
            List<Media> userStories = entry.getValue();
            User author = userMap.get(authorId);
            if (author == null) {
                continue;
            }

            UserSummaryDto userSummary = UserSummaryDto.builder()
                    .id(author.getId())
                    .username(author.getUsername())
                    .avatarUrl(mediaUrlBuilder.buildMediaUrl(author.getAvatarKey()))
                    .followedByMe(followedAuthorIds.contains(author.getId()))
                    .requestedByMe(requestedAuthorIds.contains(author.getId()))
                    .build();

            List<StoryItemDto> storyItems = new ArrayList<>();
            boolean hasUnseen = false;

            for (Media m : userStories) {
                boolean seen = seenMediaIds.contains(m.getId());
                if (!seen) {
                    hasUnseen = true;
                }
                storyItems.add(StoryItemDto.builder()
                        .id(m.getId())
                        .mediaUrl(mediaUrlBuilder.buildMediaUrl(m.getR2Key()))
                        .mediaKind(m.getMediaKind())
                        .createdAt(m.getCreatedAt())
                        .expiresAt(m.getExpiresAt())
                        .seen(seen)
                        .build());
            }

            StoryGroupDto groupDto = StoryGroupDto.builder()
                    .user(userSummary)
                    .hasUnseen(hasUnseen)
                    .stories(storyItems)
                    .build();

            if (authorId.equals(currentUserId)) {
                myGroup = groupDto;
            } else {
                groups.add(groupDto);
            }
        }

        // Group sorting:
        // 1. My group first (if exists)
        // 2. hasUnseen = true, newest story time DESC
        // 3. hasUnseen = false, newest story time DESC
        List<StoryGroupDto> sortedGroups = new ArrayList<>();
        if (myGroup != null) {
            sortedGroups.add(myGroup);
        }

        List<StoryGroupDto> unseenGroups = groups.stream()
                .filter(StoryGroupDto::isHasUnseen)
                .sorted((g1, g2) -> getNewestStoryTime(g2).compareTo(getNewestStoryTime(g1)))
                .toList();

        List<StoryGroupDto> seenGroups = groups.stream()
                .filter(g -> !g.isHasUnseen())
                .sorted((g1, g2) -> getNewestStoryTime(g2).compareTo(getNewestStoryTime(g1)))
                .toList();

        sortedGroups.addAll(unseenGroups);
        sortedGroups.addAll(seenGroups);

        return ItemsResponse.of(sortedGroups);
    }

    private Instant getNewestStoryTime(StoryGroupDto group) {
        if (group.getStories() == null || group.getStories().isEmpty()) {
            return Instant.EPOCH;
        }
        return group.getStories().get(group.getStories().size() - 1).getCreatedAt();
    }

    @Transactional
    public void markStorySeen(Long currentUserId, Long storyId) {
        Media media = mediaRepository.findById(storyId)
                .orElseThrow(() -> new NotFoundException("Story not found: " + storyId));

        if (media.getType() != MediaType.STORY) {
            throw new NotFoundException("Media is not a story: " + storyId);
        }

        if (media.getExpiresAt() != null && media.getExpiresAt().isBefore(Instant.now())) {
            throw new NotFoundException("Story has expired: " + storyId);
        }

        if (!storyViewRepository.existsByUserIdAndMediaId(currentUserId, storyId)) {
            storyViewRepository.save(StoryView.builder()
                    .userId(currentUserId)
                    .mediaId(storyId)
                    .viewedAt(Instant.now())
                    .build());
        }
    }
}
