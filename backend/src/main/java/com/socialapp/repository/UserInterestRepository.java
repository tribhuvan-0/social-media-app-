package com.socialapp.repository;

import com.socialapp.entity.UserInterest;
import com.socialapp.entity.UserInterestId;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

@Repository
public interface UserInterestRepository extends JpaRepository<UserInterest, UserInterestId> {

    List<UserInterest> findByUserId(Long userId);

    Optional<UserInterest> findByUserIdAndTag(Long userId, String tag);

    @Query("SELECT ui FROM UserInterest ui WHERE ui.userId = :userId ORDER BY ui.score DESC")
    List<UserInterest> findTopInterestsByUserId(@Param("userId") Long userId, Pageable pageable);

    @Modifying
    @Query("UPDATE UserInterest ui SET ui.score = ui.score * :factor, ui.updatedAt = :now")
    int decayAllScores(@Param("factor") double factor, @Param("now") Instant now);

    @Modifying
    @Query("DELETE FROM UserInterest ui WHERE ui.score > -0.5 AND ui.score < 0.5")
    int pruneLowScores();
}
