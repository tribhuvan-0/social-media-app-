package com.socialapp.dto.common;

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
public class PagedResponse<T> {

    @Builder.Default
    private List<T> items = Collections.emptyList();

    @Builder.Default
    private boolean hasNext = false;

    public static <T> PagedResponse<T> of(List<T> items, boolean hasNext) {
        return PagedResponse.<T>builder()
                .items(items)
                .hasNext(hasNext)
                .build();
    }
}
