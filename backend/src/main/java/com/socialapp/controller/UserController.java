package com.socialapp.controller;

import com.socialapp.dto.auth.MeResponse;
import com.socialapp.dto.common.PagedResponse;
import com.socialapp.dto.media.GridItemDto;
import com.socialapp.dto.media.ItemsResponse;
import com.socialapp.dto.user.*;
import com.socialapp.security.CurrentUser;
import com.socialapp.security.CustomUserDetails;
import com.socialapp.security.SecurityUtils;
import com.socialapp.service.UserService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/users")
@RequiredArgsConstructor
public class UserController {

    private final UserService userService;

    @GetMapping("/suggested")
    public ResponseEntity<ItemsResponse<UserSummaryDto>> getSuggestedUsers(
            @CurrentUser CustomUserDetails userDetails
    ) {
        Long currentUserId = userDetails != null ? userDetails.getId() : SecurityUtils.getCurrentUserId();
        ItemsResponse<UserSummaryDto> suggested = userService.getSuggestedUsers(currentUserId);
        return ResponseEntity.ok(suggested);
    }

    @GetMapping("/{id}/profile")
    public ResponseEntity<ProfileDto> getProfile(
            @PathVariable("id") Long id,
            @CurrentUser CustomUserDetails userDetails
    ) {
        Long currentUserId = userDetails != null ? userDetails.getId() : SecurityUtils.getCurrentUserId();
        ProfileDto profile = userService.getProfile(currentUserId, id);
        return ResponseEntity.ok(profile);
    }

    @GetMapping("/{id}/posts")
    public ResponseEntity<PagedResponse<GridItemDto>> getUserPosts(
            @PathVariable("id") Long id,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "18") int size,
            @CurrentUser CustomUserDetails userDetails
    ) {
        Long currentUserId = userDetails != null ? userDetails.getId() : SecurityUtils.getCurrentUserId();
        PagedResponse<GridItemDto> posts = userService.getUserPosts(currentUserId, id, page, size);
        return ResponseEntity.ok(posts);
    }

    @GetMapping("/{id}/followers")
    public ResponseEntity<PagedResponse<UserSummaryDto>> getUserFollowers(
            @PathVariable("id") Long id,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size,
            @CurrentUser CustomUserDetails userDetails
    ) {
        Long currentUserId = userDetails != null ? userDetails.getId() : SecurityUtils.getCurrentUserId();
        PagedResponse<UserSummaryDto> followers = userService.getUserFollowers(currentUserId, id, page, size);
        return ResponseEntity.ok(followers);
    }

    @GetMapping("/{id}/following")
    public ResponseEntity<PagedResponse<UserSummaryDto>> getUserFollowing(
            @PathVariable("id") Long id,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size,
            @CurrentUser CustomUserDetails userDetails
    ) {
        Long currentUserId = userDetails != null ? userDetails.getId() : SecurityUtils.getCurrentUserId();
        PagedResponse<UserSummaryDto> following = userService.getUserFollowing(currentUserId, id, page, size);
        return ResponseEntity.ok(following);
    }

    @PostMapping("/{id}/follow")
    public ResponseEntity<FollowResponse> followUser(
            @PathVariable("id") Long id,
            @CurrentUser CustomUserDetails userDetails
    ) {
        Long currentUserId = userDetails != null ? userDetails.getId() : SecurityUtils.getCurrentUserId();
        FollowResponse response = userService.followUser(currentUserId, id);
        return ResponseEntity.ok(response);
    }

    @DeleteMapping("/{id}/follow")
    public ResponseEntity<FollowResponse> unfollowUser(
            @PathVariable("id") Long id,
            @CurrentUser CustomUserDetails userDetails
    ) {
        Long currentUserId = userDetails != null ? userDetails.getId() : SecurityUtils.getCurrentUserId();
        FollowResponse response = userService.unfollowUser(currentUserId, id);
        return ResponseEntity.ok(response);
    }

    @PutMapping("/me")
    public ResponseEntity<MeResponse> updateProfile(
            @Valid @RequestBody UpdateProfileRequest request,
            @CurrentUser CustomUserDetails userDetails
    ) {
        Long currentUserId = userDetails != null ? userDetails.getId() : SecurityUtils.getCurrentUserId();
        MeResponse response = userService.updateProfile(currentUserId, request);
        return ResponseEntity.ok(response);
    }

    @PutMapping("/me/avatar")
    public ResponseEntity<MeResponse> updateAvatar(
            @Valid @RequestBody UpdateAvatarRequest request,
            @CurrentUser CustomUserDetails userDetails
    ) {
        Long currentUserId = userDetails != null ? userDetails.getId() : SecurityUtils.getCurrentUserId();
        MeResponse response = userService.updateAvatar(currentUserId, request);
        return ResponseEntity.ok(response);
    }

    @PutMapping("/me/settings")
    public ResponseEntity<SettingsResponse> updateSettings(
            @RequestBody UpdateSettingsRequest request,
            @CurrentUser CustomUserDetails userDetails
    ) {
        Long currentUserId = userDetails != null ? userDetails.getId() : SecurityUtils.getCurrentUserId();
        SettingsResponse response = userService.updateSettings(currentUserId, request);
        return ResponseEntity.ok(response);
    }
}
