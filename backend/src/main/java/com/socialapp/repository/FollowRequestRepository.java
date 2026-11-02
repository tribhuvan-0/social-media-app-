package com.socialapp.repository;

import com.socialapp.entity.FollowRequest;
import com.socialapp.entity.FollowRequestId;
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
public interface FollowRequestRepository extends JpaRepository<FollowRequest, FollowRequestId> {

    boolean existsByRequesterIdAndTargetId(Long requesterId, Long targetId);

    Optional<FollowRequest> findByRequesterIdAndTargetId(Long requesterId, Long targetId);

    @Modifying
    @Query("DELETE FROM FollowRequest r WHERE r.requesterId = :requesterId AND r.targetId = :targetId")
    void deleteByRequesterIdAndTargetId(@Param("requesterId") Long requesterId, @Param("targetId") Long targetId);

    Page<FollowRequest> findByTargetIdOrderByCreatedAtDesc(Long targetId, Pageable pageable);

    List<FollowRequest> findByTargetId(Long targetId);

    @Query("SELECT r.targetId FROM FollowRequest r WHERE r.requesterId = :requesterId AND r.targetId IN :targetIds")
    List<Long> findRequestedTargetIdsByRequesterIdAndTargetIdIn(
            @Param("requesterId") Long requesterId,
            @Param("targetIds") Collection<Long> targetIds
    );
}
