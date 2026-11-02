package com.socialapp.controller;

import com.socialapp.dto.media.ItemsResponse;
import com.socialapp.dto.media.StoryGroupDto;
import com.socialapp.security.CurrentUser;
import com.socialapp.security.CustomUserDetails;
import com.socialapp.security.SecurityUtils;
import com.socialapp.service.StoriesService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/stories")
@RequiredArgsConstructor
public class StoriesController {

    private final StoriesService storiesService;

    @GetMapping
    public ResponseEntity<ItemsResponse<StoryGroupDto>> getStories(
            @CurrentUser CustomUserDetails userDetails
    ) {
        Long currentUserId = userDetails != null ? userDetails.getId() : SecurityUtils.getCurrentUserId();
        ItemsResponse<StoryGroupDto> stories = storiesService.getStories(currentUserId);
        return ResponseEntity.ok(stories);
    }

    @PostMapping("/{id}/seen")
    public ResponseEntity<Void> markStorySeen(
            @PathVariable("id") Long id,
            @CurrentUser CustomUserDetails userDetails
    ) {
        Long currentUserId = userDetails != null ? userDetails.getId() : SecurityUtils.getCurrentUserId();
        storiesService.markStorySeen(currentUserId, id);
        return ResponseEntity.noContent().build();
    }
}
