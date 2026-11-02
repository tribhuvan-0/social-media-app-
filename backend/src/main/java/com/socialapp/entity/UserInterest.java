package com.socialapp.entity;

import jakarta.persistence.*;
import lombok.*;

import java.time.Instant;

@Entity
@Table(name = "user_interests")
@IdClass(UserInterestId.class)
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class UserInterest {

    @Id
    @Column(name = "user_id", nullable = false)
    private Long userId;

    @Id
    @Column(name = "tag", nullable = false, length = 50)
    private String tag;

    @Column(name = "score", nullable = false)
    @Builder.Default
    private double score = 0.0;

    @Column(name = "updated_at", nullable = false)
    @Builder.Default
    private Instant updatedAt = Instant.now();
}
