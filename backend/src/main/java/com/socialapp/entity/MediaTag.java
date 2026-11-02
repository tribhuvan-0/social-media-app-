package com.socialapp.entity;

import jakarta.persistence.*;
import lombok.*;

@Entity
@Table(name = "media_tags")
@IdClass(MediaTagId.class)
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class MediaTag {

    @Id
    @Column(name = "media_id", nullable = false)
    private Long mediaId;

    @Id
    @Column(name = "tag", nullable = false, length = 50)
    private String tag;
}
