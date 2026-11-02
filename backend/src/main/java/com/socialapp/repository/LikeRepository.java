package com.socialapp.repository;

import com.socialapp.entity.Like;
import com.socialapp.entity.LikeId;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.Collection;
import java.util.List;
import java.util.Optional;

@Repository
public interface LikeRepository extends JpaRepository<Like, LikeId> {

    boolean existsByUserIdAndMediaId(Long userId, Long mediaId);

    Optional<Like> findByUserIdAndMediaId(Long userId, Long mediaId);

    @Modifying
    @Query("DELETE FROM Like l WHERE l.userId = :userId AND l.mediaId = :mediaId")
    void deleteByUserIdAndMediaId(@Param("userId") Long userId, @Param("mediaId") Long mediaId);

    @Modifying
    @Query("DELETE FROM Like l WHERE l.mediaId = :mediaId")
    void deleteByMediaId(@Param("mediaId") Long mediaId);

    @Query("SELECT l.mediaId FROM Like l WHERE l.userId = :userId AND l.mediaId IN :mediaIds")
    List<Long> findLikedMediaIdsByUserIdAndMediaIdIn(
            @Param("userId") Long userId,
            @Param("mediaIds") Collection<Long> mediaIds
    );
}
