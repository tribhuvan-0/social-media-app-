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
public class UpdateSettingsRequest {

    @JsonProperty("isPrivate")
    private Boolean isPrivate;

    @JsonProperty("notificationsEnabled")
    private Boolean notificationsEnabled;
}
