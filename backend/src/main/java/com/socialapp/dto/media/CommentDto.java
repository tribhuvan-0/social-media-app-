package com.socialapp.dto.media;

import com.socialapp.dto.user.UserSummaryDto;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CommentDto {

    private Long id;
    private Long mediaId;
    private String text;
    private Instant createdAt;
    private UserSummaryDto user;
}
