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
public class SettingsResponse {

    @JsonProperty("isPrivate")
    private boolean isPrivate;

    @JsonProperty("notificationsEnabled")
    private boolean notificationsEnabled;
}
