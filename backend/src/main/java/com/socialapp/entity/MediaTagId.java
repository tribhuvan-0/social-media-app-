package com.socialapp.entity;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class MediaTagId implements Serializable {
    private Long mediaId;
    private String tag;
}
