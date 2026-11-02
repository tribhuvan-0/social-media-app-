package com.socialapp.controller;

import com.socialapp.dto.common.PagedResponse;
import com.socialapp.dto.user.UserSummaryDto;
import com.socialapp.security.CurrentUser;
import com.socialapp.security.CustomUserDetails;
import com.socialapp.security.SecurityUtils;
import com.socialapp.service.UserService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/follow-requests")
@RequiredArgsConstructor
public class FollowRequestController {

    private final UserService userService;

    @GetMapping
    public ResponseEntity<PagedResponse<UserSummaryDto>> getFollowRequests(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size,
            @CurrentUser CustomUserDetails userDetails
    ) {
        Long currentUserId = userDetails != null ? userDetails.getId() : SecurityUtils.getCurrentUserId();
        PagedResponse<UserSummaryDto> requests = userService.getFollowRequests(currentUserId, page, size);
        return ResponseEntity.ok(requests);
    }

    @PostMapping("/{userId}/accept")
    public ResponseEntity<Void> acceptFollowRequest(
            @PathVariable("userId") Long userId,
            @CurrentUser CustomUserDetails userDetails
    ) {
        Long currentUserId = userDetails != null ? userDetails.getId() : SecurityUtils.getCurrentUserId();
        userService.acceptFollowRequest(currentUserId, userId);
        return ResponseEntity.noContent().build();
    }

    @PostMapping("/{userId}/decline")
    public ResponseEntity<Void> declineFollowRequest(
            @PathVariable("userId") Long userId,
            @CurrentUser CustomUserDetails userDetails
    ) {
        Long currentUserId = userDetails != null ? userDetails.getId() : SecurityUtils.getCurrentUserId();
        userService.declineFollowRequest(currentUserId, userId);
        return ResponseEntity.noContent().build();
    }
}
