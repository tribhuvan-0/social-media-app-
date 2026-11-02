package com.socialapp.service;

import com.socialapp.dto.auth.MeResponse;
import com.socialapp.dto.common.PagedResponse;
import com.socialapp.dto.media.GridItemDto;
import com.socialapp.dto.media.ItemsResponse;
import com.socialapp.dto.user.*;
import com.socialapp.entity.Follow;
import com.socialapp.entity.FollowRequest;
import com.socialapp.entity.Media;
import com.socialapp.entity.User;
import com.socialapp.entity.enums.MediaType;
import com.socialapp.exception.BadRequestException;
import com.socialapp.exception.ConflictException;
import com.socialapp.exception.ForbiddenException;
import com.socialapp.exception.NotFoundException;
import com.socialapp.mapper.MediaMapper;
import com.socialapp.mapper.UserMapper;
import com.socialapp.repository.FollowRepository;
import com.socialapp.repository.FollowRequestRepository;
import com.socialapp.repository.MediaRepository;
import com.socialapp.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.*;

@Slf4j
@Service
@RequiredArgsConstructor
public class UserService {

    private final UserRepository userRepository;
    private final FollowRepository followRepository;
    private final FollowRequestRepository followRequestRepository;
    private final MediaRepository mediaRepository;
    private final StorageService storageService;
    private final RecommendationService recommendationService;
    private final UserMapper userMapper;
    private final MediaMapper mediaMapper;

    @Transactional(readOnly = true)
    public ProfileDto getProfile(Long currentUserId, Long targetUserId) {
        User targetUser = userRepository.findById(targetUserId)
                .orElseThrow(() -> new NotFoundException("User not found: " + targetUserId));

        long postCount = mediaRepository.countByUserIdAndTypeIn(targetUserId, List.of(MediaType.POST, MediaType.REEL));
        long followerCount = followRepository.countByFollowingId(targetUserId);
        long followingCount = followRepository.countByFollowerId(targetUserId);

        return userMapper.toProfileDto(targetUser, currentUserId, postCount, followerCount, followingCount);
    }

    @Transactional(readOnly = true)
    public PagedResponse<GridItemDto> getUserPosts(Long currentUserId, Long targetUserId, int page, int size) {
        User targetUser = userRepository.findById(targetUserId)
                .orElseThrow(() -> new NotFoundException("User not found: " + targetUserId));

        boolean isMe = Objects.equals(currentUserId, targetUserId);
        boolean followedByMe = currentUserId != null && followRepository.existsByFollowerIdAndFollowingId(currentUserId, targetUserId);
        boolean canView = isMe || !targetUser.isPrivate() || followedByMe;

        if (!canView) {
            throw new ForbiddenException("This account is private");
        }

        if (page < 0) {
            throw new BadRequestException("Page number cannot be negative");
        }
        if (size <= 0) {
            throw new BadRequestException("Page size must be positive");
        }

        Pageable pageable = PageRequest.of(page, size, Sort.by(Sort.Direction.DESC, "createdAt"));
        Page<Media> mediaPage = mediaRepository.findByUserIdAndTypeInOrderByCreatedAtDesc(
                targetUserId,
                List.of(MediaType.POST, MediaType.REEL),
                pageable
        );

        List<GridItemDto> items = mediaMapper.toGridItemDtoList(mediaPage.getContent());
        return PagedResponse.of(items, mediaPage.hasNext());
    }

    @Transactional(readOnly = true)
    public PagedResponse<UserSummaryDto> getUserFollowers(Long currentUserId, Long targetUserId, int page, int size) {
        User targetUser = userRepository.findById(targetUserId)
                .orElseThrow(() -> new NotFoundException("User not found: " + targetUserId));

        boolean isMe = Objects.equals(currentUserId, targetUserId);
        boolean followedByMe = currentUserId != null && followRepository.existsByFollowerIdAndFollowingId(currentUserId, targetUserId);
        boolean canView = isMe || !targetUser.isPrivate() || followedByMe;

        if (!canView) {
            throw new ForbiddenException("This account is private");
        }

        if (page < 0) {
            throw new BadRequestException("Page number cannot be negative");
        }
        if (size <= 0) {
            throw new BadRequestException("Page size must be positive");
        }

        Pageable pageable = PageRequest.of(page, size, Sort.by(Sort.Direction.DESC, "createdAt"));
        Page<Follow> followPage = followRepository.findByFollowingIdOrderByCreatedAtDesc(targetUserId, pageable);

        List<Long> followerIds = followPage.getContent().stream().map(Follow::getFollowerId).toList();
        List<User> followers = new ArrayList<>();
        if (!followerIds.isEmpty()) {
            Map<Long, User> userMap = new HashMap<>();
            for (User u : userRepository.findAllByIdIn(followerIds)) {
                userMap.put(u.getId(), u);
            }
            for (Long id : followerIds) {
                User u = userMap.get(id);
                if (u != null) {
                    followers.add(u);
                }
            }
        }

        List<UserSummaryDto> items = userMapper.toUserSummaryDtoList(followers, currentUserId);
        return PagedResponse.of(items, followPage.hasNext());
    }

    @Transactional(readOnly = true)
    public PagedResponse<UserSummaryDto> getUserFollowing(Long currentUserId, Long targetUserId, int page, int size) {
        User targetUser = userRepository.findById(targetUserId)
                .orElseThrow(() -> new NotFoundException("User not found: " + targetUserId));

        boolean isMe = Objects.equals(currentUserId, targetUserId);
        boolean followedByMe = currentUserId != null && followRepository.existsByFollowerIdAndFollowingId(currentUserId, targetUserId);
        boolean canView = isMe || !targetUser.isPrivate() || followedByMe;

        if (!canView) {
            throw new ForbiddenException("This account is private");
        }

        if (page < 0) {
            throw new BadRequestException("Page number cannot be negative");
        }
        if (size <= 0) {
            throw new BadRequestException("Page size must be positive");
        }

        Pageable pageable = PageRequest.of(page, size, Sort.by(Sort.Direction.DESC, "createdAt"));
        Page<Follow> followPage = followRepository.findByFollowerIdOrderByCreatedAtDesc(targetUserId, pageable);

        List<Long> followingIds = followPage.getContent().stream().map(Follow::getFollowingId).toList();
        List<User> following = new ArrayList<>();
        if (!followingIds.isEmpty()) {
            Map<Long, User> userMap = new HashMap<>();
            for (User u : userRepository.findAllByIdIn(followingIds)) {
                userMap.put(u.getId(), u);
            }
            for (Long id : followingIds) {
                User u = userMap.get(id);
                if (u != null) {
                    following.add(u);
                }
            }
        }

        List<UserSummaryDto> items = userMapper.toUserSummaryDtoList(following, currentUserId);
        return PagedResponse.of(items, followPage.hasNext());
    }

    @Transactional(readOnly = true)
    public ItemsResponse<UserSummaryDto> getSuggestedUsers(Long currentUserId) {
        List<User> candidates = userRepository.findSuggestedCandidates(currentUserId);
        if (candidates.isEmpty()) {
            return ItemsResponse.of(Collections.emptyList());
        }

        // Order by follower count DESC, then newest createdAt DESC
        candidates.sort((u1, u2) -> {
            long c1 = followRepository.countByFollowingId(u1.getId());
            long c2 = followRepository.countByFollowingId(u2.getId());
            int cmp = Long.compare(c2, c1);
            if (cmp != 0) {
                return cmp;
            }
            return u2.getCreatedAt().compareTo(u1.getCreatedAt());
        });

        List<User> top10 = candidates.stream().limit(10).toList();
        List<UserSummaryDto> dtos = userMapper.toUserSummaryDtoList(top10, currentUserId);
        return ItemsResponse.of(dtos);
    }

    @Transactional
    public FollowResponse followUser(Long currentUserId, Long targetUserId) {
        if (Objects.equals(currentUserId, targetUserId)) {
            throw new BadRequestException("Cannot follow yourself");
        }

        User targetUser = userRepository.findById(targetUserId)
                .orElseThrow(() -> new NotFoundException("User not found: " + targetUserId));

        boolean alreadyFollowing = followRepository.existsByFollowerIdAndFollowingId(currentUserId, targetUserId);
        if (alreadyFollowing) {
            long count = followRepository.countByFollowingId(targetUserId);
            return FollowResponse.builder().following(true).requested(false).followerCount(count).build();
        }

        if (!targetUser.isPrivate()) {
            // Public user: follow immediately
            followRequestRepository.deleteByRequesterIdAndTargetId(currentUserId, targetUserId);
            followRepository.save(Follow.builder()
                    .followerId(currentUserId)
                    .followingId(targetUserId)
                    .createdAt(Instant.now())
                    .build());

            recommendationService.updateInterestOnFollow(currentUserId, targetUserId);

            long count = followRepository.countByFollowingId(targetUserId);
            return FollowResponse.builder().following(true).requested(false).followerCount(count).build();
        } else {
            // Private user: create follow request
            boolean alreadyRequested = followRequestRepository.existsByRequesterIdAndTargetId(currentUserId, targetUserId);
            if (!alreadyRequested) {
                followRequestRepository.save(FollowRequest.builder()
                        .requesterId(currentUserId)
                        .targetId(targetUserId)
                        .createdAt(Instant.now())
                        .build());
            }

            long count = followRepository.countByFollowingId(targetUserId);
            return FollowResponse.builder().following(false).requested(true).followerCount(count).build();
        }
    }

    @Transactional
    public FollowResponse unfollowUser(Long currentUserId, Long targetUserId) {
        if (Objects.equals(currentUserId, targetUserId)) {
            throw new BadRequestException("Cannot unfollow yourself");
        }

        User targetUser = userRepository.findById(targetUserId)
                .orElseThrow(() -> new NotFoundException("User not found: " + targetUserId));

        if (followRepository.existsByFollowerIdAndFollowingId(currentUserId, targetUserId)) {
            followRepository.deleteByFollowerIdAndFollowingId(currentUserId, targetUserId);
        }

        if (followRequestRepository.existsByRequesterIdAndTargetId(currentUserId, targetUserId)) {
            followRequestRepository.deleteByRequesterIdAndTargetId(currentUserId, targetUserId);
        }

        long count = followRepository.countByFollowingId(targetUserId);
        return FollowResponse.builder().following(false).requested(false).followerCount(count).build();
    }

    @Transactional
    public MeResponse updateProfile(Long currentUserId, UpdateProfileRequest request) {
        User user = userRepository.findById(currentUserId)
                .orElseThrow(() -> new NotFoundException("User not found: " + currentUserId));

        if (request.getUsername() != null && !request.getUsername().isBlank()) {
            String newUsername = request.getUsername().toLowerCase(Locale.ROOT).trim();
            if (!newUsername.matches("^[a-zA-Z0-9_]{3,30}$")) {
                throw new BadRequestException("Username must be 3-30 characters with letters, digits, and underscores only");
            }
            if (!newUsername.equalsIgnoreCase(user.getUsername())) {
                Optional<User> existing = userRepository.findByUsername(newUsername);
                if (existing.isPresent() && !existing.get().getId().equals(currentUserId)) {
                    throw new ConflictException("Username is already taken");
                }
                user.setUsername(newUsername);
            }
        }

        if (request.getBio() != null) {
            if (request.getBio().length() > 150) {
                throw new BadRequestException("Bio must not exceed 150 characters");
            }
            user.setBio(request.getBio().trim());
        }

        User saved = userRepository.save(user);
        return userMapper.toMeResponse(saved);
    }

    @Transactional
    public MeResponse updateAvatar(Long currentUserId, UpdateAvatarRequest request) {
        User user = userRepository.findById(currentUserId)
                .orElseThrow(() -> new NotFoundException("User not found: " + currentUserId));

        String r2Key = request.getR2Key();
        String expectedPrefixUpper = "AVATAR/" + currentUserId + "/";
        String expectedPrefixLower = "avatar/" + currentUserId + "/";

        if (r2Key == null || (!r2Key.startsWith(expectedPrefixUpper) && !r2Key.startsWith(expectedPrefixLower))) {
            throw new ForbiddenException("Invalid avatar key prefix for user");
        }

        if (!storageService.exists(r2Key)) {
            throw new NotFoundException("Avatar file not found in storage: " + r2Key);
        }

        String oldAvatarKey = user.getAvatarKey();
        if (oldAvatarKey != null && !oldAvatarKey.equals(r2Key)) {
            try {
                storageService.delete(oldAvatarKey);
            } catch (Exception ex) {
                log.warn("Failed to delete old avatar {}: {}", oldAvatarKey, ex.getMessage());
            }
        }

        user.setAvatarKey(r2Key);
        User saved = userRepository.save(user);
        return userMapper.toMeResponse(saved);
    }

    @Transactional
    public SettingsResponse updateSettings(Long currentUserId, UpdateSettingsRequest request) {
        User user = userRepository.findById(currentUserId)
                .orElseThrow(() -> new NotFoundException("User not found: " + currentUserId));

        boolean oldPrivate = user.isPrivate();
        boolean newPrivate = request.getIsPrivate() != null ? request.getIsPrivate() : oldPrivate;
        boolean newNotifications = request.getNotificationsEnabled() != null ? request.getNotificationsEnabled() : user.isNotificationsEnabled();

        // When switching private to public: auto-accept all pending follow requests
        if (oldPrivate && !newPrivate) {
            List<FollowRequest> pendingRequests = followRequestRepository.findByTargetId(currentUserId);
            for (FollowRequest req : pendingRequests) {
                if (!followRepository.existsByFollowerIdAndFollowingId(req.getRequesterId(), currentUserId)) {
                    followRepository.save(Follow.builder()
                            .followerId(req.getRequesterId())
                            .followingId(currentUserId)
                            .createdAt(Instant.now())
                            .build());

                    recommendationService.updateInterestOnFollow(req.getRequesterId(), currentUserId);
                }
            }
            followRequestRepository.deleteAll(pendingRequests);
        }

        user.setPrivate(newPrivate);
        user.setNotificationsEnabled(newNotifications);
        userRepository.save(user);

        return SettingsResponse.builder()
                .isPrivate(newPrivate)
                .notificationsEnabled(newNotifications)
                .build();
    }

    @Transactional(readOnly = true)
    public PagedResponse<UserSummaryDto> getFollowRequests(Long currentUserId, int page, int size) {
        if (page < 0) {
            throw new BadRequestException("Page number cannot be negative");
        }
        if (size <= 0) {
            throw new BadRequestException("Page size must be positive");
        }

        Pageable pageable = PageRequest.of(page, size, Sort.by(Sort.Direction.DESC, "createdAt"));
        Page<FollowRequest> requestPage = followRequestRepository.findByTargetIdOrderByCreatedAtDesc(currentUserId, pageable);

        List<Long> requesterIds = requestPage.getContent().stream().map(FollowRequest::getRequesterId).toList();
        List<User> requesters = new ArrayList<>();
        if (!requesterIds.isEmpty()) {
            Map<Long, User> userMap = new HashMap<>();
            for (User u : userRepository.findAllByIdIn(requesterIds)) {
                userMap.put(u.getId(), u);
            }
            for (Long id : requesterIds) {
                User u = userMap.get(id);
                if (u != null) {
                    requesters.add(u);
                }
            }
        }

        List<UserSummaryDto> items = userMapper.toUserSummaryDtoList(requesters, currentUserId);
        return PagedResponse.of(items, requestPage.hasNext());
    }

    @Transactional
    public void acceptFollowRequest(Long currentUserId, Long requesterId) {
        FollowRequest request = followRequestRepository.findByRequesterIdAndTargetId(requesterId, currentUserId)
                .orElseThrow(() -> new NotFoundException("Follow request not found for user: " + requesterId));

        followRequestRepository.delete(request);

        if (!followRepository.existsByFollowerIdAndFollowingId(requesterId, currentUserId)) {
            followRepository.save(Follow.builder()
                    .followerId(requesterId)
                    .followingId(currentUserId)
                    .createdAt(Instant.now())
                    .build());

            recommendationService.updateInterestOnFollow(requesterId, currentUserId);
        }
    }

    @Transactional
    public void declineFollowRequest(Long currentUserId, Long requesterId) {
        FollowRequest request = followRequestRepository.findByRequesterIdAndTargetId(requesterId, currentUserId)
                .orElseThrow(() -> new NotFoundException("Follow request not found for user: " + requesterId));

        followRequestRepository.delete(request);
    }
}
