package com.socialapp.controller;

import com.socialapp.dto.common.PagedResponse;
import com.socialapp.dto.upload.MediaCardDto;
import com.socialapp.exception.BadRequestException;
import com.socialapp.security.CurrentUser;
import com.socialapp.security.CustomUserDetails;
import com.socialapp.security.SecurityUtils;
import com.socialapp.service.RecommendationService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Collections;
import java.util.HashSet;
import java.util.Set;

@RestController
@RequestMapping("/api/reels")
@RequiredArgsConstructor
public class ReelsController {

    private final RecommendationService recommendationService;

    @GetMapping
    public ResponseEntity<PagedResponse<MediaCardDto>> getReels(
            @RequestParam(defaultValue = "5") int size,
            @RequestParam(required = false) String exclude,
            @CurrentUser CustomUserDetails userDetails
    ) {
        Long currentUserId = userDetails != null ? userDetails.getId() : SecurityUtils.getCurrentUserId();

        Set<Long> excludeIds = new HashSet<>();
        if (exclude != null && !exclude.isBlank()) {
            String[] tokens = exclude.split(",");
            if (tokens.length > 100) {
                throw new BadRequestException("Exclude list cannot contain more than 100 IDs");
            }
            for (String token : tokens) {
                String trimmed = token.trim();
                if (!trimmed.isEmpty()) {
                    try {
                        excludeIds.add(Long.parseLong(trimmed));
                    } catch (NumberFormatException ignored) {
                        // Ignore non-numeric tokens
                    }
                }
            }
        }

        PagedResponse<MediaCardDto> response = recommendationService.getRecommendedReels(currentUserId, size, excludeIds);
        return ResponseEntity.ok(response);
    }
}
