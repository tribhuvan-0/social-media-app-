package com.socialapp.repository;

import com.socialapp.entity.MediaTag;
import com.socialapp.entity.MediaTagId;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.Collection;
import java.util.List;

@Repository
public interface MediaTagRepository extends JpaRepository<MediaTag, MediaTagId> {

    List<MediaTag> findByMediaId(Long mediaId);

    List<MediaTag> findByMediaIdIn(Collection<Long> mediaIds);

    @Modifying
    @Query("DELETE FROM MediaTag mt WHERE mt.mediaId = :mediaId")
    void deleteByMediaId(@Param("mediaId") Long mediaId);

    @Query("SELECT mt.tag FROM MediaTag mt WHERE mt.mediaId IN :mediaIds GROUP BY mt.tag ORDER BY COUNT(mt.tag) DESC")
    List<String> findTopTagsInMediaIds(@Param("mediaIds") Collection<Long> mediaIds, Pageable pageable);
}
