package com.socialapp.entity;

import jakarta.persistence.*;
import lombok.*;

import java.time.Instant;

@Entity
@Table(name = "media_views")
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class MediaView {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "user_id", nullable = false)
    private Long userId;

    @Column(name = "media_id", nullable = false)
    private Long mediaId;

    @Column(name = "watch_ms", nullable = false)
    private long watchMs;

    @Column(name = "duration_ms", nullable = false)
    private long durationMs;

    @Column(name = "completed", nullable = false)
    @Builder.Default
    private boolean completed = false;

    @Column(name = "viewed_at", nullable = false, updatable = false)
    @Builder.Default
    private Instant viewedAt = Instant.now();
}
