package com.socialapp.entity;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class StoryViewId implements Serializable {
    private Long userId;
    private Long mediaId;
}
