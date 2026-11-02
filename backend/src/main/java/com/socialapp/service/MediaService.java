package com.socialapp.service;

import com.socialapp.dto.common.PagedResponse;
import com.socialapp.dto.media.*;
import com.socialapp.dto.upload.MediaCardDto;
import com.socialapp.entity.*;
import com.socialapp.entity.enums.MediaType;
import com.socialapp.exception.BadRequestException;
import com.socialapp.exception.ForbiddenException;
import com.socialapp.exception.NotFoundException;
import com.socialapp.mapper.CommentMapper;
import com.socialapp.mapper.MediaMapper;
import com.socialapp.repository.*;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.Objects;

@Slf4j
@Service
@RequiredArgsConstructor
public class MediaService {

    private final MediaRepository mediaRepository;
    private final UserRepository userRepository;
    private final LikeRepository likeRepository;
    private final CommentRepository commentRepository;
    private final ShareRepository shareRepository;
    private final MediaViewRepository mediaViewRepository;
    private final StoryViewRepository storyViewRepository;
    private final MediaTagRepository mediaTagRepository;
    private final FollowRepository followRepository;
    private final StorageService storageService;
    private final RecommendationService recommendationService;
    private final MediaMapper mediaMapper;
    private final CommentMapper commentMapper;

    @Value("${app.base-url:http://localhost:8080}")
    private String appBaseUrl;

    @Transactional(readOnly = true)
    public MediaCardDto getMedia(Long currentUserId, Long mediaId) {
        Media media = mediaRepository.findById(mediaId)
                .orElseThrow(() -> new NotFoundException("Media not found: " + mediaId));

        checkPrivacyAccess(currentUserId, media.getUserId());
        return mediaMapper.toMediaCardDto(media, currentUserId);
    }

    @Transactional
    public void deleteMedia(Long currentUserId, Long mediaId) {
        Media media = mediaRepository.findById(mediaId)
                .orElseThrow(() -> new NotFoundException("Media not found: " + mediaId));

        if (!Objects.equals(media.getUserId(), currentUserId)) {
            throw new ForbiddenException("Cannot delete media owned by another user");
        }

        // Delete storage assets (catch exceptions so DB delete is not blocked)
        try {
            storageService.delete(media.getR2Key());
            if (media.getThumbnailKey() != null && !media.getThumbnailKey().equals(media.getR2Key())) {
                storageService.delete(media.getThumbnailKey());
            }
        } catch (Exception ex) {
            log.warn("Failed to delete storage asset for media {}: {}", mediaId, ex.getMessage());
        }

        // Cascade delete dependent rows
        mediaTagRepository.deleteByMediaId(mediaId);
        likeRepository.deleteByMediaId(mediaId);
        commentRepository.deleteByMediaId(mediaId);
        shareRepository.deleteByMediaId(mediaId);
        storyViewRepository.deleteByMediaId(mediaId);
        mediaViewRepository.deleteByMediaId(mediaId);
        mediaRepository.delete(media);
    }

    @Transactional
    public LikeResponse likeMedia(Long currentUserId, Long mediaId) {
        Media media = mediaRepository.findById(mediaId)
                .orElseThrow(() -> new NotFoundException("Media not found: " + mediaId));

        checkPrivacyAccess(currentUserId, media.getUserId());

        if (!likeRepository.existsByUserIdAndMediaId(currentUserId, mediaId)) {
            likeRepository.save(Like.builder()
                    .userId(currentUserId)
                    .mediaId(mediaId)
                    .createdAt(Instant.now())
                    .build());

            mediaRepository.incrementLikeCount(mediaId);
            recommendationService.updateInterestForMedia(currentUserId, mediaId, 4.0);
        }

        int likeCount = mediaRepository.getLikeCount(mediaId).orElse(media.getLikeCount());
        return LikeResponse.builder()
                .liked(true)
                .likeCount(likeCount)
                .build();
    }

    @Transactional
    public LikeResponse unlikeMedia(Long currentUserId, Long mediaId) {
        Media media = mediaRepository.findById(mediaId)
                .orElseThrow(() -> new NotFoundException("Media not found: " + mediaId));

        if (likeRepository.existsByUserIdAndMediaId(currentUserId, mediaId)) {
            likeRepository.deleteByUserIdAndMediaId(currentUserId, mediaId);
            mediaRepository.decrementLikeCount(mediaId);
            recommendationService.updateInterestForMedia(currentUserId, mediaId, -4.0);
        }

        int likeCount = mediaRepository.getLikeCount(mediaId).orElse(media.getLikeCount());
        return LikeResponse.builder()
                .liked(false)
                .likeCount(likeCount)
                .build();
    }

    @Transactional
    public ShareResponse shareMedia(Long currentUserId, Long mediaId) {
        Media media = mediaRepository.findById(mediaId)
                .orElseThrow(() -> new NotFoundException("Media not found: " + mediaId));

        checkPrivacyAccess(currentUserId, media.getUserId());

        shareRepository.save(Share.builder()
                .userId(currentUserId)
                .mediaId(mediaId)
                .createdAt(Instant.now())
                .build());

        mediaRepository.incrementShareCount(mediaId);
        recommendationService.updateInterestForMedia(currentUserId, mediaId, 6.0);

        int shareCount = mediaRepository.getShareCount(mediaId).orElse(media.getShareCount());
        String shareUrl = appBaseUrl.replaceAll("/+$", "") + "/m/" + mediaId;

        return ShareResponse.builder()
                .shareCount(shareCount)
                .shareUrl(shareUrl)
                .build();
    }

    @Transactional
    public void recordView(Long currentUserId, Long mediaId, ViewEventRequest request) {
        Media media = mediaRepository.findById(mediaId)
                .orElseThrow(() -> new NotFoundException("Media not found: " + mediaId));

        // View tracking is ignored for STORY media and own media (per docs.md line 260)
        if (media.getType() == MediaType.STORY || Objects.equals(media.getUserId(), currentUserId)) {
            return;
        }

        long watchMs = request.getWatchMs() != null ? request.getWatchMs() : 0L;
        long durationMs = request.getDurationMs() != null ? request.getDurationMs() : 0L;
        boolean completed = Boolean.TRUE.equals(request.getCompleted());

        mediaViewRepository.save(MediaView.builder()
                .userId(currentUserId)
                .mediaId(mediaId)
                .watchMs(watchMs)
                .durationMs(durationMs)
                .completed(completed)
                .viewedAt(Instant.now())
                .build());

        mediaRepository.incrementViewCount(mediaId);

        // Interest update based on watch telemetry
        double delta = 0.0;
        boolean watchedFully = completed || (durationMs > 0 && watchMs >= (long) (0.8 * durationMs));
        if (watchedFully) {
            delta += 2.0;
            if (watchMs > durationMs) {
                delta += 1.0; // Extra loop
            }
        } else if (watchMs >= 2000 && (durationMs == 0 || watchMs < (long) (0.8 * durationMs))) {
            delta += 0.5; // Watched between 2s and 80%
        } else if (watchMs < 2000) {
            delta += -2.0; // Skipped
        }

        recommendationService.updateInterestForMedia(currentUserId, mediaId, delta);
    }

    @Transactional(readOnly = true)
    public PagedResponse<CommentDto> getComments(Long currentUserId, Long mediaId, int page, int size) {
        Media media = mediaRepository.findById(mediaId)
                .orElseThrow(() -> new NotFoundException("Media not found: " + mediaId));

        checkPrivacyAccess(currentUserId, media.getUserId());

        if (page < 0) {
            throw new BadRequestException("Page number cannot be negative");
        }
        if (size <= 0) {
            throw new BadRequestException("Page size must be positive");
        }

        Pageable pageable = PageRequest.of(page, size, Sort.by(Sort.Direction.ASC, "createdAt"));
        Page<Comment> commentPage = commentRepository.findByMediaIdOrderByCreatedAtAsc(mediaId, pageable);

        return PagedResponse.of(
                commentMapper.toCommentDtoList(commentPage.getContent(), currentUserId),
                commentPage.hasNext()
        );
    }

    @Transactional
    public CommentDto addComment(Long currentUserId, Long mediaId, AddCommentRequest request) {
        Media media = mediaRepository.findById(mediaId)
                .orElseThrow(() -> new NotFoundException("Media not found: " + mediaId));

        checkPrivacyAccess(currentUserId, media.getUserId());

        if (request.getText() == null || request.getText().trim().isEmpty() || request.getText().length() > 500) {
            throw new BadRequestException("Comment text must be between 1 and 500 characters");
        }

        Comment comment = commentRepository.save(Comment.builder()
                .userId(currentUserId)
                .mediaId(mediaId)
                .text(request.getText().trim())
                .createdAt(Instant.now())
                .build());

        mediaRepository.incrementCommentCount(mediaId);
        recommendationService.updateInterestForMedia(currentUserId, mediaId, 5.0);

        return commentMapper.toCommentDto(comment, currentUserId);
    }

    @Transactional
    public void deleteComment(Long currentUserId, Long commentId) {
        Comment comment = commentRepository.findById(commentId)
                .orElseThrow(() -> new NotFoundException("Comment not found: " + commentId));

        Media media = mediaRepository.findById(comment.getMediaId())
                .orElseThrow(() -> new NotFoundException("Media for comment not found: " + comment.getMediaId()));

        boolean isAuthor = Objects.equals(comment.getUserId(), currentUserId);
        boolean isMediaOwner = Objects.equals(media.getUserId(), currentUserId);

        if (!isAuthor && !isMediaOwner) {
            throw new ForbiddenException("Cannot delete another user's comment");
        }

        commentRepository.delete(comment);
        mediaRepository.decrementCommentCount(media.getId());
    }

    private void checkPrivacyAccess(Long currentUserId, Long authorId) {
        User author = userRepository.findById(authorId)
                .orElseThrow(() -> new NotFoundException("Author not found: " + authorId));

        if (author.isPrivate()) {
            boolean isOwner = Objects.equals(currentUserId, authorId);
            boolean isFollower = currentUserId != null && followRepository.existsByFollowerIdAndFollowingId(currentUserId, authorId);
            if (!isOwner && !isFollower) {
                throw new ForbiddenException("This account is private");
            }
        }
    }
}
