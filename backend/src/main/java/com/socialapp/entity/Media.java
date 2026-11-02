package com.socialapp.entity;

import com.socialapp.entity.enums.MediaKind;
import com.socialapp.entity.enums.MediaType;
import jakarta.persistence.*;
import lombok.*;

import java.time.Instant;

@Entity
@Table(name = "media")
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class Media {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "user_id", nullable = false)
    private Long userId;

    @Enumerated(EnumType.STRING)
    @Column(name = "type", nullable = false, length = 20)
    private MediaType type;

    @Enumerated(EnumType.STRING)
    @Column(name = "media_kind", nullable = false, length = 20)
    private MediaKind mediaKind;

    @Column(name = "r2_key", nullable = false, length = 500)
    private String r2Key;

    @Column(name = "thumbnail_key", length = 500)
    private String thumbnailKey;

    @Column(name = "caption", length = 2200)
    private String caption;

    @Column(name = "created_at", nullable = false, updatable = false)
    @Builder.Default
    private Instant createdAt = Instant.now();

    @Column(name = "expires_at")
    private Instant expiresAt;

    @Column(name = "like_count", nullable = false)
    @Builder.Default
    private int likeCount = 0;

    @Column(name = "comment_count", nullable = false)
    @Builder.Default
    private int commentCount = 0;

    @Column(name = "share_count", nullable = false)
    @Builder.Default
    private int shareCount = 0;

    @Column(name = "view_count", nullable = false)
    @Builder.Default
    private int viewCount = 0;
}
