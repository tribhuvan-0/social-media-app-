package com.socialapp.repository;

import com.socialapp.entity.User;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.Collection;
import java.util.List;
import java.util.Optional;

@Repository
public interface UserRepository extends JpaRepository<User, Long> {

    Optional<User> findByUsername(String username);

    Optional<User> findByEmail(String email);

    boolean existsByUsername(String username);

    boolean existsByEmail(String email);

    List<User> findAllByIdIn(Collection<Long> ids);

    @Query("SELECT u FROM User u WHERE u.id != :currentUserId " +
           "AND u.id NOT IN (SELECT f.followingId FROM Follow f WHERE f.followerId = :currentUserId) " +
           "AND u.id NOT IN (SELECT r.targetId FROM FollowRequest r WHERE r.requesterId = :currentUserId) " +
           "AND (u.isPrivate = false OR u.id IN (SELECT DISTINCT m.userId FROM Media m WHERE m.type IN (com.socialapp.entity.enums.MediaType.POST, com.socialapp.entity.enums.MediaType.REEL)))")
    List<User> findSuggestedCandidates(@Param("currentUserId") Long currentUserId);
}
