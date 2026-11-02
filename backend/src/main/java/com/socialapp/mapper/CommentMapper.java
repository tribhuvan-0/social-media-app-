package com.socialapp.mapper;

import com.socialapp.dto.media.CommentDto;
import com.socialapp.dto.user.UserSummaryDto;
import com.socialapp.entity.Comment;
import com.socialapp.entity.User;
import com.socialapp.repository.FollowRepository;
import com.socialapp.repository.FollowRequestRepository;
import com.socialapp.repository.UserRepository;
import com.socialapp.util.MediaUrlBuilder;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.util.*;
import java.util.function.Function;
import java.util.stream.Collectors;

@Component
@RequiredArgsConstructor
public class CommentMapper {

    private final MediaUrlBuilder mediaUrlBuilder;
    private final UserRepository userRepository;
    private final FollowRepository followRepository;
    private final FollowRequestRepository followRequestRepository;

    public CommentDto toCommentDto(Comment comment, Long currentUserId) {
        if (comment == null) {
            return null;
        }
        List<CommentDto> dtos = toCommentDtoList(Collections.singletonList(comment), currentUserId);
        return dtos.isEmpty() ? null : dtos.get(0);
    }

    public List<CommentDto> toCommentDtoList(List<Comment> comments, Long currentUserId) {
        if (comments == null || comments.isEmpty()) {
            return Collections.emptyList();
        }

        List<Long> authorIds = comments.stream().map(Comment::getUserId).filter(Objects::nonNull).distinct().toList();
        Map<Long, User> userMap = userRepository.findAllByIdIn(authorIds).stream()
                .collect(Collectors.toMap(User::getId, Function.identity(), (u1, u2) -> u1));

        Set<Long> followedAuthorIds = (currentUserId != null && !authorIds.isEmpty())
                ? new HashSet<>(followRepository.findFollowingIdsByFollowerIdAndFollowingIdIn(currentUserId, authorIds))
                : Collections.emptySet();

        Set<Long> requestedAuthorIds = (currentUserId != null && !authorIds.isEmpty())
                ? new HashSet<>(followRequestRepository.findRequestedTargetIdsByRequesterIdAndTargetIdIn(currentUserId, authorIds))
                : Collections.emptySet();

        List<CommentDto> result = new ArrayList<>(comments.size());
        for (Comment comment : comments) {
            User author = userMap.get(comment.getUserId());
            UserSummaryDto userSummary = null;
            if (author != null) {
                userSummary = UserSummaryDto.builder()
                        .id(author.getId())
                        .username(author.getUsername())
                        .avatarUrl(mediaUrlBuilder.buildMediaUrl(author.getAvatarKey()))
                        .followedByMe(followedAuthorIds.contains(author.getId()))
                        .requestedByMe(requestedAuthorIds.contains(author.getId()))
                        .build();
            }

            CommentDto commentDto = CommentDto.builder()
                    .id(comment.getId())
                    .mediaId(comment.getMediaId())
                    .text(comment.getText())
                    .createdAt(comment.getCreatedAt())
                    .user(userSummary)
                    .build();

            result.add(commentDto);
        }

        return result;
    }
}
