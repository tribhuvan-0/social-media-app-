package com.socialapp.repository;

import com.socialapp.entity.Comment;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

@Repository
public interface CommentRepository extends JpaRepository<Comment, Long> {

    Page<Comment> findByMediaIdOrderByCreatedAtAsc(Long mediaId, Pageable pageable);

    @Modifying
    @Query("DELETE FROM Comment c WHERE c.mediaId = :mediaId")
    void deleteByMediaId(@Param("mediaId") Long mediaId);

    long countByMediaId(Long mediaId);
}
