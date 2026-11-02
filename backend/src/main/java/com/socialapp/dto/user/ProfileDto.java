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
public class ProfileDto {

    private Long id;
    private String username;
    private String bio;
    private String avatarUrl;

    @JsonProperty("isPrivate")
    private boolean isPrivate;

    @JsonProperty("isMe")
    private boolean isMe;

    private long postCount;
    private long followerCount;
    private long followingCount;

    @JsonProperty("followedByMe")
    private boolean followedByMe;

    @JsonProperty("requestedByMe")
    private boolean requestedByMe;

    @JsonProperty("canView")
    private boolean canView;
}
