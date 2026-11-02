package com.socialapp.repository;

import com.socialapp.entity.StoryView;
import com.socialapp.entity.StoryViewId;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.Collection;
import java.util.List;

@Repository
public interface StoryViewRepository extends JpaRepository<StoryView, StoryViewId> {

    boolean existsByUserIdAndMediaId(Long userId, Long mediaId);

    @Query("SELECT v.mediaId FROM StoryView v WHERE v.userId = :userId AND v.mediaId IN :mediaIds")
    List<Long> findViewedMediaIdsByUserIdAndMediaIdIn(
            @Param("userId") Long userId,
            @Param("mediaIds") Collection<Long> mediaIds
    );

    @Modifying
    @Query("DELETE FROM StoryView v WHERE v.mediaId = :mediaId")
    void deleteByMediaId(@Param("mediaId") Long mediaId);
}
