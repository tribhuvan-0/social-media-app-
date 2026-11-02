package com.socialapp.mapper;

import com.socialapp.dto.media.GridItemDto;
import com.socialapp.dto.upload.MediaCardDto;
import com.socialapp.dto.user.UserSummaryDto;
import com.socialapp.entity.Media;
import com.socialapp.entity.MediaTag;
import com.socialapp.entity.User;
import com.socialapp.repository.*;
import com.socialapp.util.MediaUrlBuilder;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.util.*;
import java.util.function.Function;
import java.util.stream.Collectors;

@Component
@RequiredArgsConstructor
public class MediaMapper {

    private final MediaUrlBuilder mediaUrlBuilder;
    private final UserRepository userRepository;
    private final MediaTagRepository mediaTagRepository;
    private final LikeRepository likeRepository;
    private final FollowRepository followRepository;
    private final FollowRequestRepository followRequestRepository;

    public MediaCardDto toMediaCardDto(Media media, Long currentUserId) {
        if (media == null) {
            return null;
        }
        List<MediaCardDto> dtos = toMediaCardDtoList(Collections.singletonList(media), currentUserId);
        return dtos.isEmpty() ? null : dtos.get(0);
    }

    public List<MediaCardDto> toMediaCardDtoList(List<Media> mediaList, Long currentUserId) {
        if (mediaList == null || mediaList.isEmpty()) {
            return Collections.emptyList();
        }

        List<Long> mediaIds = mediaList.stream().map(Media::getId).filter(Objects::nonNull).distinct().toList();
        List<Long> authorIds = mediaList.stream().map(Media::getUserId).filter(Objects::nonNull).distinct().toList();

        // 1. Batch load Users for authors
        Map<Long, User> userMap = userRepository.findAllByIdIn(authorIds).stream()
                .collect(Collectors.toMap(User::getId, Function.identity(), (u1, u2) -> u1));

        // 2. Batch load Tags for media
        Map<Long, List<String>> tagMap = new HashMap<>();
        if (!mediaIds.isEmpty()) {
            List<MediaTag> allTags = mediaTagRepository.findByMediaIdIn(mediaIds);
            for (MediaTag mt : allTags) {
                tagMap.computeIfAbsent(mt.getMediaId(), k -> new ArrayList<>()).add(mt.getTag());
            }
        }

        // 3. Batch load interaction states (likedByMe, followedByMe, requestedByMe)
        Set<Long> likedMediaIds = (currentUserId != null && !mediaIds.isEmpty())
                ? new HashSet<>(likeRepository.findLikedMediaIdsByUserIdAndMediaIdIn(currentUserId, mediaIds))
                : Collections.emptySet();

        Set<Long> followedAuthorIds = (currentUserId != null && !authorIds.isEmpty())
                ? new HashSet<>(followRepository.findFollowingIdsByFollowerIdAndFollowingIdIn(currentUserId, authorIds))
                : Collections.emptySet();

        Set<Long> requestedAuthorIds = (currentUserId != null && !authorIds.isEmpty())
                ? new HashSet<>(followRequestRepository.findRequestedTargetIdsByRequesterIdAndTargetIdIn(currentUserId, authorIds))
                : Collections.emptySet();

        // 4. Map media to DTO
        List<MediaCardDto> result = new ArrayList<>(mediaList.size());
        for (Media media : mediaList) {
            User author = userMap.get(media.getUserId());
            UserSummaryDto userSummary = null;
            if (author != null) {
                boolean followed = followedAuthorIds.contains(author.getId());
                boolean requested = requestedAuthorIds.contains(author.getId());
                userSummary = UserSummaryDto.builder()
                        .id(author.getId())
                        .username(author.getUsername())
                        .avatarUrl(mediaUrlBuilder.buildMediaUrl(author.getAvatarKey()))
                        .followedByMe(followed)
                        .requestedByMe(requested)
                        .build();
            }

            MediaCardDto cardDto = MediaCardDto.builder()
                    .id(media.getId())
                    .type(media.getType())
                    .mediaKind(media.getMediaKind())
                    .mediaUrl(mediaUrlBuilder.buildMediaUrl(media.getR2Key()))
                    .thumbnailUrl(mediaUrlBuilder.buildThumbnailUrl(media.getThumbnailKey()))
                    .caption(media.getCaption())
                    .tags(tagMap.getOrDefault(media.getId(), Collections.emptyList()))
                    .createdAt(media.getCreatedAt())
                    .likeCount(media.getLikeCount())
                    .commentCount(media.getCommentCount())
                    .shareCount(media.getShareCount())
                    .likedByMe(likedMediaIds.contains(media.getId()))
                    .user(userSummary)
                    .build();

            result.add(cardDto);
        }

        return result;
    }

    public GridItemDto toGridItemDto(Media media) {
        if (media == null) {
            return null;
        }
        return GridItemDto.builder()
                .id(media.getId())
                .type(media.getType())
                .mediaKind(media.getMediaKind())
                .thumbnailUrl(mediaUrlBuilder.buildThumbnailUrl(media.getThumbnailKey()))
                .build();
    }

    public List<GridItemDto> toGridItemDtoList(List<Media> mediaList) {
        if (mediaList == null || mediaList.isEmpty()) {
            return Collections.emptyList();
        }
        return mediaList.stream().map(this::toGridItemDto).toList();
    }
}
