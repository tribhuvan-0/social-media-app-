package com.socialapp.dto.auth;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class MeResponse {

    private Long id;
    private String username;
    private String email;
    private String bio;
    private String avatarUrl;

    @JsonProperty("isPrivate")
    private boolean isPrivate;

    @JsonProperty("notificationsEnabled")
    private boolean notificationsEnabled;
}
