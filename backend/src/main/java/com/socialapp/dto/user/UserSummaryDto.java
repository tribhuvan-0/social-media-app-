package com.socialapp.dto.user;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class UserSummaryDto {

    private Long id;
    private String username;
    private String avatarUrl;

    @JsonProperty("followedByMe")
    private boolean followedByMe;

    @JsonProperty("requestedByMe")
    private boolean requestedByMe;
}
