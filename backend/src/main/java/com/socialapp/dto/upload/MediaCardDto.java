package com.socialapp.dto.upload;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.socialapp.dto.user.UserSummaryDto;
import com.socialapp.entity.enums.MediaKind;
import com.socialapp.entity.enums.MediaType;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.util.List;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class MediaCardDto {

    private Long id;
    private MediaType type;
    private MediaKind mediaKind;
    private String mediaUrl;
    private String thumbnailUrl;
    private String caption;
    private List<String> tags;
    private Instant createdAt;
    private int likeCount;
    private int commentCount;
    private int shareCount;

    @JsonProperty("likedByMe")
    private boolean likedByMe;

    private UserSummaryDto user;
}
