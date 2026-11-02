package com.socialapp.dto.upload;

import com.socialapp.entity.enums.MediaType;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ConfirmUploadRequest {

    @NotBlank(message = "R2 key is required")
    private String r2Key;

    @NotNull(message = "Media type is required")
    private MediaType type;

    @Size(max = 2200, message = "Caption cannot exceed 2200 characters")
    private String caption;
}
