package com.socialapp.mapper;

import com.socialapp.dto.auth.MeResponse;
import com.socialapp.dto.user.ProfileDto;
import com.socialapp.dto.user.UserSummaryDto;
import com.socialapp.entity.User;
import com.socialapp.repository.FollowRepository;
import com.socialapp.repository.FollowRequestRepository;
import com.socialapp.util.MediaUrlBuilder;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.util.*;

@Component
@RequiredArgsConstructor
public class UserMapper {

    private final MediaUrlBuilder mediaUrlBuilder;
    private final FollowRepository followRepository;
    private final FollowRequestRepository followRequestRepository;

    public MeResponse toMeResponse(User user) {
        if (user == null) {
            return null;
        }
        return MeResponse.builder()
                .id(user.getId())
                .username(user.getUsername())
                .email(user.getEmail())
                .bio(user.getBio())
                .avatarUrl(mediaUrlBuilder.buildMediaUrl(user.getAvatarKey()))
                .isPrivate(user.isPrivate())
                .notificationsEnabled(user.isNotificationsEnabled())
                .build();
    }

    public UserSummaryDto toUserSummaryDto(User user, boolean followedByMe, boolean requestedByMe) {
        if (user == null) {
            return null;
        }
        return UserSummaryDto.builder()
                .id(user.getId())
                .username(user.getUsername())
                .avatarUrl(mediaUrlBuilder.buildMediaUrl(user.getAvatarKey()))
                .followedByMe(followedByMe)
                .requestedByMe(requestedByMe)
                .build();
    }

    public List<UserSummaryDto> toUserSummaryDtoList(List<User> users, Long currentUserId) {
        if (users == null || users.isEmpty()) {
            return Collections.emptyList();
        }

        List<Long> targetIds = users.stream().map(User::getId).filter(Objects::nonNull).distinct().toList();
        Set<Long> followedIds = (currentUserId != null && !targetIds.isEmpty())
                ? new HashSet<>(followRepository.findFollowingIdsByFollowerIdAndFollowingIdIn(currentUserId, targetIds))
                : Collections.emptySet();
        Set<Long> requestedIds = (currentUserId != null && !targetIds.isEmpty())
                ? new HashSet<>(followRequestRepository.findRequestedTargetIdsByRequesterIdAndTargetIdIn(currentUserId, targetIds))
                : Collections.emptySet();

        return users.stream()
                .map(u -> toUserSummaryDto(u, followedIds.contains(u.getId()), requestedIds.contains(u.getId())))
                .toList();
    }

    public ProfileDto toProfileDto(User user, Long currentUserId, long postCount, long followerCount, long followingCount) {
        if (user == null) {
            return null;
        }
        boolean isMe = currentUserId != null && currentUserId.equals(user.getId());
        boolean followedByMe = (currentUserId != null && !isMe) && followRepository.existsByFollowerIdAndFollowingId(currentUserId, user.getId());
        boolean requestedByMe = (currentUserId != null && !isMe) && followRequestRepository.existsByRequesterIdAndTargetId(currentUserId, user.getId());
        boolean canView = isMe || !user.isPrivate() || followedByMe;

        return ProfileDto.builder()
                .id(user.getId())
                .username(user.getUsername())
                .bio(user.getBio())
                .avatarUrl(mediaUrlBuilder.buildMediaUrl(user.getAvatarKey()))
                .isPrivate(user.isPrivate())
                .isMe(isMe)
                .postCount(postCount)
                .followerCount(followerCount)
                .followingCount(followingCount)
                .followedByMe(followedByMe)
                .requestedByMe(requestedByMe)
                .canView(canView)
                .build();
    }
}
