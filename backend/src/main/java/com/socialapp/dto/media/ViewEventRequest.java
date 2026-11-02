package com.socialapp.dto.media;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ViewEventRequest {

    private Long watchMs;
    private Long durationMs;
    private Boolean completed;
}
