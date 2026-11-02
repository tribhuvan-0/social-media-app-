package com.socialapp.dto.media;

import com.socialapp.dto.user.UserSummaryDto;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.ArrayList;
import java.util.List;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class StoryGroupDto {

    private UserSummaryDto user;
    private boolean hasUnseen;

    @Builder.Default
    private List<StoryItemDto> stories = new ArrayList<>();
}
