package com.socialapp.repository;

import com.socialapp.entity.Share;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

@Repository
public interface ShareRepository extends JpaRepository<Share, Long> {

    @Modifying
    @Query("DELETE FROM Share s WHERE s.mediaId = :mediaId")
    void deleteByMediaId(@Param("mediaId") Long mediaId);
}
