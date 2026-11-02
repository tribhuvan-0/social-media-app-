package com.socialapp.dto.media;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.Collections;
import java.util.List;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ItemsResponse<T> {

    @Builder.Default
    private List<T> items = Collections.emptyList();

    public static <T> ItemsResponse<T> of(List<T> items) {
        return ItemsResponse.<T>builder()
                .items(items != null ? items : Collections.emptyList())
                .build();
    }
}
