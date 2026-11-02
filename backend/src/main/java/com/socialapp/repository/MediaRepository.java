package com.socialapp.repository;

import com.socialapp.entity.Media;
import com.socialapp.entity.enums.MediaType;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.Collection;
import java.util.List;
import java.util.Optional;

@Repository
public interface MediaRepository extends JpaRepository<Media, Long> {

    // Atomic Counter Updates
    @Modifying
    @Query("UPDATE Media m SET m.likeCount = m.likeCount + 1 WHERE m.id = :id")
    int incrementLikeCount(@Param("id") Long id);

    @Modifying
    @Query("UPDATE Media m SET m.likeCount = CASE WHEN m.likeCount > 0 THEN m.likeCount - 1 ELSE 0 END WHERE m.id = :id")
    int decrementLikeCount(@Param("id") Long id);

    @Modifying
    @Query("UPDATE Media m SET m.commentCount = m.commentCount + 1 WHERE m.id = :id")
    int incrementCommentCount(@Param("id") Long id);

    @Modifying
    @Query("UPDATE Media m SET m.commentCount = CASE WHEN m.commentCount > 0 THEN m.commentCount - 1 ELSE 0 END WHERE m.id = :id")
    int decrementCommentCount(@Param("id") Long id);

    @Modifying
    @Query("UPDATE Media m SET m.shareCount = m.shareCount + 1 WHERE m.id = :id")
    int incrementShareCount(@Param("id") Long id);

    @Modifying
    @Query("UPDATE Media m SET m.viewCount = m.viewCount + 1 WHERE m.id = :id")
    int incrementViewCount(@Param("id") Long id);

    // Atomic Counter Read Projections
    @Query("SELECT m.likeCount FROM Media m WHERE m.id = :id")
    Optional<Integer> getLikeCount(@Param("id") Long id);

    @Query("SELECT m.commentCount FROM Media m WHERE m.id = :id")
    Optional<Integer> getCommentCount(@Param("id") Long id);

    @Query("SELECT m.shareCount FROM Media m WHERE m.id = :id")
    Optional<Integer> getShareCount(@Param("id") Long id);

    @Query("SELECT m.viewCount FROM Media m WHERE m.id = :id")
    Optional<Integer> getViewCount(@Param("id") Long id);

    // Feed Query: POST and REEL from followed users and self, newest first
    Page<Media> findByUserIdInAndTypeInOrderByCreatedAtDesc(
            Collection<Long> userIds,
            Collection<MediaType> types,
            Pageable pageable
    );

    // User Profile Grid Query: POST and REEL by userId, newest first
    Page<Media> findByUserIdAndTypeInOrderByCreatedAtDesc(
            Long userId,
            Collection<MediaType> types,
            Pageable pageable
    );

    // Post Count (POST and REEL)
    long countByUserIdAndTypeIn(Long userId, Collection<MediaType> types);

    // Active Stories Query: expiresAt > now for userIds, oldest to newest
    List<Media> findByUserIdInAndTypeAndExpiresAtAfterOrderByCreatedAtAsc(
            Collection<Long> userIds,
            MediaType type,
            Instant now
    );

    // Expired Stories for Scheduled Cleanup
    List<Media> findByTypeAndExpiresAtBefore(MediaType type, Instant cutoff);

    // Candidate Reels for Recommendation Engine
    @Query("SELECT m FROM Media m WHERE m.type = com.socialapp.entity.enums.MediaType.REEL " +
           "AND m.userId != :currentUserId " +
           "AND (m.userId IN (SELECT u.id FROM User u WHERE u.isPrivate = false) " +
           "     OR m.userId IN (SELECT f.followingId FROM Follow f WHERE f.followerId = :currentUserId))")
    List<Media> findReelCandidatesForUser(@Param("currentUserId") Long currentUserId);

    // Find all reels of a creator (used for computing creator's top tags on follow)
    List<Media> findByUserIdAndType(Long userId, MediaType type);
}
