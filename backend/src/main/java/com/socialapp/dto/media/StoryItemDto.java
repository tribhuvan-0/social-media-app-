package com.socialapp.dto.media;

import com.socialapp.entity.enums.MediaKind;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class StoryItemDto {

    private Long id;
    private String mediaUrl;
    private MediaKind mediaKind;
    private Instant createdAt;
    private Instant expiresAt;
    private boolean seen;
}
