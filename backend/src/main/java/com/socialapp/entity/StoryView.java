package com.socialapp.entity;

import jakarta.persistence.*;
import lombok.*;

import java.time.Instant;

@Entity
@Table(name = "story_views")
@IdClass(StoryViewId.class)
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class StoryView {

    @Id
    @Column(name = "user_id", nullable = false)
    private Long userId;

    @Id
    @Column(name = "media_id", nullable = false)
    private Long mediaId;

    @Column(name = "viewed_at", nullable = false, updatable = false)
    @Builder.Default
    private Instant viewedAt = Instant.now();
}
