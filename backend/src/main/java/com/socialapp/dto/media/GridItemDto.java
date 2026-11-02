package com.socialapp.dto.media;

import com.socialapp.entity.enums.MediaKind;
import com.socialapp.entity.enums.MediaType;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class GridItemDto {

    private Long id;
    private MediaType type;
    private MediaKind mediaKind;
    private String thumbnailUrl;
}
