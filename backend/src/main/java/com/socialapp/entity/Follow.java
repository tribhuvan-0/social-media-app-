package com.socialapp.entity;

import jakarta.persistence.*;
import lombok.*;

import java.time.Instant;

@Entity
@Table(name = "follows")
@IdClass(FollowId.class)
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class Follow {

    @Id
    @Column(name = "follower_id", nullable = false)
    private Long followerId;

    @Id
    @Column(name = "following_id", nullable = false)
    private Long followingId;

    @Column(name = "created_at", nullable = false, updatable = false)
    @Builder.Default
    private Instant createdAt = Instant.now();
}
