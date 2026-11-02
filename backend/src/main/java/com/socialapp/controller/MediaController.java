package com.socialapp.controller;

import com.socialapp.dto.common.PagedResponse;
import com.socialapp.dto.media.*;
import com.socialapp.dto.upload.MediaCardDto;
import com.socialapp.security.CurrentUser;
import com.socialapp.security.CustomUserDetails;
import com.socialapp.security.SecurityUtils;
import com.socialapp.service.MediaService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequiredArgsConstructor
public class MediaController {

    private final MediaService mediaService;

    @GetMapping("/api/media/{id}")
    public ResponseEntity<MediaCardDto> getMedia(
            @PathVariable("id") Long id,
            @CurrentUser CustomUserDetails userDetails
    ) {
        Long currentUserId = userDetails != null ? userDetails.getId() : SecurityUtils.getCurrentUserId();
        MediaCardDto cardDto = mediaService.getMedia(currentUserId, id);
        return ResponseEntity.ok(cardDto);
    }

    @DeleteMapping("/api/media/{id}")
    public ResponseEntity<Void> deleteMedia(
            @PathVariable("id") Long id,
            @CurrentUser CustomUserDetails userDetails
    ) {
        Long currentUserId = userDetails != null ? userDetails.getId() : SecurityUtils.getCurrentUserId();
        mediaService.deleteMedia(currentUserId, id);
        return ResponseEntity.noContent().build();
    }

    @PostMapping("/api/media/{id}/like")
    public ResponseEntity<LikeResponse> likeMedia(
            @PathVariable("id") Long id,
            @CurrentUser CustomUserDetails userDetails
    ) {
        Long currentUserId = userDetails != null ? userDetails.getId() : SecurityUtils.getCurrentUserId();
        LikeResponse response = mediaService.likeMedia(currentUserId, id);
        return ResponseEntity.ok(response);
    }

    @DeleteMapping("/api/media/{id}/like")
    public ResponseEntity<LikeResponse> unlikeMedia(
            @PathVariable("id") Long id,
            @CurrentUser CustomUserDetails userDetails
    ) {
        Long currentUserId = userDetails != null ? userDetails.getId() : SecurityUtils.getCurrentUserId();
        LikeResponse response = mediaService.unlikeMedia(currentUserId, id);
        return ResponseEntity.ok(response);
    }

    @PostMapping("/api/media/{id}/share")
    public ResponseEntity<ShareResponse> shareMedia(
            @PathVariable("id") Long id,
            @CurrentUser CustomUserDetails userDetails
    ) {
        Long currentUserId = userDetails != null ? userDetails.getId() : SecurityUtils.getCurrentUserId();
        ShareResponse response = mediaService.shareMedia(currentUserId, id);
        return ResponseEntity.ok(response);
    }

    @PostMapping("/api/media/{id}/view")
    public ResponseEntity<Void> recordView(
            @PathVariable("id") Long id,
            @RequestBody(required = false) ViewEventRequest request,
            @CurrentUser CustomUserDetails userDetails
    ) {
        Long currentUserId = userDetails != null ? userDetails.getId() : SecurityUtils.getCurrentUserId();
        mediaService.recordView(currentUserId, id, request != null ? request : new ViewEventRequest());
        return ResponseEntity.noContent().build();
    }

    @GetMapping("/api/media/{id}/comments")
    public ResponseEntity<PagedResponse<CommentDto>> getComments(
            @PathVariable("id") Long id,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size,
            @CurrentUser CustomUserDetails userDetails
    ) {
        Long currentUserId = userDetails != null ? userDetails.getId() : SecurityUtils.getCurrentUserId();
        PagedResponse<CommentDto> comments = mediaService.getComments(currentUserId, id, page, size);
        return ResponseEntity.ok(comments);
    }

    @PostMapping("/api/media/{id}/comments")
    public ResponseEntity<CommentDto> addComment(
            @PathVariable("id") Long id,
            @Valid @RequestBody AddCommentRequest request,
            @CurrentUser CustomUserDetails userDetails
    ) {
        Long currentUserId = userDetails != null ? userDetails.getId() : SecurityUtils.getCurrentUserId();
        CommentDto commentDto = mediaService.addComment(currentUserId, id, request);
        return ResponseEntity.status(HttpStatus.CREATED).body(commentDto);
    }

    @DeleteMapping("/api/comments/{id}")
    public ResponseEntity<Void> deleteComment(
            @PathVariable("id") Long id,
            @CurrentUser CustomUserDetails userDetails
    ) {
        Long currentUserId = userDetails != null ? userDetails.getId() : SecurityUtils.getCurrentUserId();
        mediaService.deleteComment(currentUserId, id);
        return ResponseEntity.noContent().build();
    }
}
