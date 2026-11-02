package com.socialapp.controller;

import com.socialapp.dto.upload.ConfirmUploadRequest;
import com.socialapp.dto.upload.MediaCardDto;
import com.socialapp.dto.upload.PresignRequest;
import com.socialapp.dto.upload.PresignResponse;
import com.socialapp.dto.user.UserSummaryDto;
import com.socialapp.entity.Media;
import com.socialapp.entity.MediaTag;
import com.socialapp.entity.User;
import com.socialapp.entity.enums.MediaKind;
import com.socialapp.entity.enums.MediaType;
import com.socialapp.entity.enums.UploadType;
import com.socialapp.exception.BadRequestException;
import com.socialapp.exception.ForbiddenException;
import com.socialapp.exception.NotFoundException;
import com.socialapp.repository.UserRepository;
import com.socialapp.security.CurrentUser;
import com.socialapp.security.CustomUserDetails;
import com.socialapp.security.SecurityUtils;
import com.socialapp.service.FfmpegThumbnailService;
import com.socialapp.service.StorageService;
import com.socialapp.util.MediaUrlBuilder;
import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Slf4j
@RestController
@RequestMapping("/api/uploads")
@RequiredArgsConstructor
public class UploadController {

    private static final long MAX_IMAGE_SIZE = 10L * 1024 * 1024;    // 10 MB
    private static final long MAX_VIDEO_SIZE = 100L * 1024 * 1024;   // 100 MB
    private static final Set<String> ALLOWED_IMAGE_TYPES = Set.of("image/jpeg", "image/png");
    private static final Set<String> ALLOWED_VIDEO_TYPES = Set.of("video/mp4");
    private static final Pattern HASHTAG_PATTERN = Pattern.compile("#([A-Za-z0-9_]{1,30})");

    private final StorageService storageService;
    private final FfmpegThumbnailService ffmpegThumbnailService;
    private final MediaUrlBuilder mediaUrlBuilder;
    private final UserRepository userRepository;

    @PersistenceContext
    private EntityManager entityManager;

    @PostMapping("/presign")
    public ResponseEntity<PresignResponse> presign(
            @CurrentUser CustomUserDetails userDetails,
            @Valid @RequestBody PresignRequest request
    ) {
        Long currentUserId = userDetails != null ? userDetails.getId() : SecurityUtils.getCurrentUserId();

        String contentType = request.getContentType();
        if (contentType == null || (!ALLOWED_IMAGE_TYPES.contains(contentType) && !ALLOWED_VIDEO_TYPES.contains(contentType))) {
            throw new BadRequestException("Unsupported content type: " + contentType + ". Allowed: image/jpeg, image/png, video/mp4");
        }

        Long fileSize = request.getFileSize();
        if (fileSize == null || fileSize <= 0) {
            throw new BadRequestException("File size must be greater than 0");
        }

        UploadType uploadType = request.getType();
        if (uploadType == null) {
            throw new BadRequestException("Upload type is required");
        }

        boolean isVideo = ALLOWED_VIDEO_TYPES.contains(contentType);

        if (uploadType == UploadType.REEL && !isVideo) {
            throw new BadRequestException("REEL must be video/mp4");
        }

        if (uploadType == UploadType.AVATAR && isVideo) {
            throw new BadRequestException("AVATAR must be an image");
        }

        if (isVideo && fileSize > MAX_VIDEO_SIZE) {
            throw new BadRequestException("Video file size cannot exceed 100MB");
        }

        if (!isVideo && fileSize > MAX_IMAGE_SIZE) {
            throw new BadRequestException("Image file size cannot exceed 10MB");
        }

        String originalName = request.getFileName();
        String cleanName = (originalName != null && !originalName.isBlank())
                ? originalName.replaceAll("[^a-zA-Z0-9._-]", "_")
                : (isVideo ? "video.mp4" : "image.jpg");

        String r2Key = uploadType.name() + "/" + currentUserId + "/" + UUID.randomUUID() + "-" + cleanName;
        String uploadUrl = storageService.generatePresignedUploadUrl(r2Key, contentType, fileSize);

        return ResponseEntity.ok(PresignResponse.builder()
                .uploadUrl(uploadUrl)
                .r2Key(r2Key)
                .build());
    }

    @PostMapping("/confirm")
    @Transactional
    public ResponseEntity<MediaCardDto> confirm(
            @CurrentUser CustomUserDetails userDetails,
            @Valid @RequestBody ConfirmUploadRequest request
    ) {
        Long currentUserId = userDetails != null ? userDetails.getId() : SecurityUtils.getCurrentUserId();

        String r2Key = request.getR2Key();
        MediaType mediaType = request.getType();
        String expectedPrefix = mediaType.name() + "/" + currentUserId + "/";

        if (!r2Key.startsWith(expectedPrefix)) {
            log.warn("User {} attempted to confirm asset with key {} not matching prefix {}", currentUserId, r2Key, expectedPrefix);
            throw new ForbiddenException("Cannot confirm asset: key prefix does not match authenticated user ID and media type");
        }

        if (!storageService.exists(r2Key)) {
            throw new NotFoundException("Uploaded file not found in storage: " + r2Key);
        }

        long actualSize = storageService.getContentLength(r2Key);
        boolean isVideo = r2Key.toLowerCase().endsWith(".mp4");
        long maxAllowed = isVideo ? MAX_VIDEO_SIZE : MAX_IMAGE_SIZE;

        if (actualSize > maxAllowed) {
            storageService.delete(r2Key);
            throw new BadRequestException("Uploaded file exceeds maximum size limit (" + actualSize + " > " + maxAllowed + ")");
        }

        MediaKind mediaKind = isVideo ? MediaKind.VIDEO : MediaKind.IMAGE;

        Media media = Media.builder()
                .userId(currentUserId)
                .type(mediaType)
                .mediaKind(mediaKind)
                .r2Key(r2Key)
                .caption(request.getCaption())
                .createdAt(Instant.now())
                .likeCount(0)
                .commentCount(0)
                .shareCount(0)
                .viewCount(0)
                .build();

        if (mediaType == MediaType.STORY) {
            media.setExpiresAt(Instant.now().plus(24, ChronoUnit.HOURS));
        }

        if (mediaKind == MediaKind.IMAGE) {
            media.setThumbnailKey(r2Key);
        } else {
            media.setThumbnailKey(null);
        }

        entityManager.persist(media);
        entityManager.flush();

        // Extract hashtags from caption
        List<String> tags = new ArrayList<>();
        if (request.getCaption() != null && !request.getCaption().isBlank()) {
            Matcher matcher = HASHTAG_PATTERN.matcher(request.getCaption());
            Set<String> distinctTags = new LinkedHashSet<>();
            while (matcher.find() && distinctTags.size() < 10) {
                distinctTags.add(matcher.group(1).toLowerCase());
            }
            tags.addAll(distinctTags);
            for (String tag : tags) {
                entityManager.persist(new MediaTag(media.getId(), tag));
            }
        }

        // Trigger async video thumbnail extraction
        if (mediaKind == MediaKind.VIDEO) {
            ffmpegThumbnailService.generateThumbnailAsync(media.getId(), r2Key, currentUserId);
        }

        User user = userRepository.findById(currentUserId)
                .orElseThrow(() -> new NotFoundException("User not found: " + currentUserId));

        UserSummaryDto userSummary = UserSummaryDto.builder()
                .id(user.getId())
                .username(user.getUsername())
                .avatarUrl(mediaUrlBuilder.buildMediaUrl(user.getAvatarKey()))
                .followedByMe(false)
                .requestedByMe(false)
                .build();

        MediaCardDto cardDto = MediaCardDto.builder()
                .id(media.getId())
                .type(media.getType())
                .mediaKind(media.getMediaKind())
                .mediaUrl(mediaUrlBuilder.buildMediaUrl(media.getR2Key()))
                .thumbnailUrl(mediaUrlBuilder.buildThumbnailUrl(media.getThumbnailKey()))
                .caption(media.getCaption())
                .tags(tags)
                .createdAt(media.getCreatedAt())
                .likeCount(0)
                .commentCount(0)
                .shareCount(0)
                .likedByMe(false)
                .user(userSummary)
                .build();

        return ResponseEntity.status(HttpStatus.CREATED).body(cardDto);
    }
}
