package com.socialapp.entity;

import jakarta.persistence.*;
import lombok.*;

import java.time.Instant;

@Entity
@Table(name = "follow_requests")
@IdClass(FollowRequestId.class)
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class FollowRequest {

    @Id
    @Column(name = "requester_id", nullable = false)
    private Long requesterId;

    @Id
    @Column(name = "target_id", nullable = false)
    private Long targetId;

    @Column(name = "created_at", nullable = false, updatable = false)
    @Builder.Default
    private Instant createdAt = Instant.now();
}
