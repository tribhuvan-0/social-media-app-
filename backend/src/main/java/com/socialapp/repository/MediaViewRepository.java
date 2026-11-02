package com.socialapp.repository;

import com.socialapp.entity.MediaView;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.List;

@Repository
public interface MediaViewRepository extends JpaRepository<MediaView, Long> {

    long countByUserId(Long userId);

    @Query("SELECT DISTINCT v.mediaId FROM MediaView v WHERE v.userId = :userId AND v.viewedAt >= :since")
    List<Long> findViewedMediaIdsSince(@Param("userId") Long userId, @Param("since") Instant since);

    @Query("SELECT DISTINCT v.mediaId FROM MediaView v WHERE v.userId = :userId")
    List<Long> findAllViewedMediaIds(@Param("userId") Long userId);

    @Modifying
    @Query("DELETE FROM MediaView v WHERE v.viewedAt < :cutoff")
    int deleteByViewedAtBefore(@Param("cutoff") Instant cutoff);

    @Modifying
    @Query("DELETE FROM MediaView v WHERE v.mediaId = :mediaId")
    void deleteByMediaId(@Param("mediaId") Long mediaId);
}
