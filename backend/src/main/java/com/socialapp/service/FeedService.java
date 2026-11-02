package com.socialapp.service;

import com.socialapp.dto.common.PagedResponse;
import com.socialapp.dto.upload.MediaCardDto;
import com.socialapp.entity.Media;
import com.socialapp.entity.enums.MediaType;
import com.socialapp.exception.BadRequestException;
import com.socialapp.mapper.MediaMapper;
import com.socialapp.repository.FollowRepository;
import com.socialapp.repository.MediaRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.*;

@Slf4j
@Service
@RequiredArgsConstructor
public class FeedService {

    private final MediaRepository mediaRepository;
    private final FollowRepository followRepository;
    private final MediaMapper mediaMapper;

    @Transactional(readOnly = true)
    public PagedResponse<MediaCardDto> getFeed(Long currentUserId, int page, int size) {
        if (page < 0) {
            throw new BadRequestException("Page number cannot be negative");
        }
        if (size <= 0 || size > 50) {
            throw new BadRequestException("Page size must be between 1 and 50");
        }

        List<Long> followedIds = followRepository.findFollowingIdsByFollowerId(currentUserId);
        Set<Long> userIds = new HashSet<>(followedIds);
        userIds.add(currentUserId);

        Pageable pageable = PageRequest.of(page, size, Sort.by(Sort.Direction.DESC, "createdAt"));
        Page<Media> mediaPage = mediaRepository.findByUserIdInAndTypeInOrderByCreatedAtDesc(
                userIds,
                List.of(MediaType.POST, MediaType.REEL),
                pageable
        );

        List<MediaCardDto> items = mediaMapper.toMediaCardDtoList(mediaPage.getContent(), currentUserId);
        return PagedResponse.of(items, mediaPage.hasNext());
    }
}
