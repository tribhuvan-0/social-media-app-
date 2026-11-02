package com.socialapp.repository;

import com.socialapp.entity.Follow;
import com.socialapp.entity.FollowId;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.Collection;
import java.util.List;
import java.util.Optional;

@Repository
public interface FollowRepository extends JpaRepository<Follow, FollowId> {

    boolean existsByFollowerIdAndFollowingId(Long followerId, Long followingId);

    Optional<Follow> findByFollowerIdAndFollowingId(Long followerId, Long followingId);

    @Modifying
    @Query("DELETE FROM Follow f WHERE f.followerId = :followerId AND f.followingId = :followingId")
    void deleteByFollowerIdAndFollowingId(@Param("followerId") Long followerId, @Param("followingId") Long followingId);

    long countByFollowingId(Long followingId);

    long countByFollowerId(Long followerId);

    Page<Follow> findByFollowingIdOrderByCreatedAtDesc(Long followingId, Pageable pageable);

    Page<Follow> findByFollowerIdOrderByCreatedAtDesc(Long followerId, Pageable pageable);

    @Query("SELECT f.followingId FROM Follow f WHERE f.followerId = :followerId")
    List<Long> findFollowingIdsByFollowerId(@Param("followerId") Long followerId);

    @Query("SELECT f.followingId FROM Follow f WHERE f.followerId = :followerId AND f.followingId IN :followingIds")
    List<Long> findFollowingIdsByFollowerIdAndFollowingIdIn(
            @Param("followerId") Long followerId,
            @Param("followingIds") Collection<Long> followingIds
    );
}
