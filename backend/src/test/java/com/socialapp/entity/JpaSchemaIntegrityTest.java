package com.socialapp.entity;

import com.socialapp.entity.enums.MediaKind;
import com.socialapp.entity.enums.MediaType;
import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.test.context.TestPropertySource;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest
@TestPropertySource(locations = "classpath:application-test.properties")
@Transactional
class JpaSchemaIntegrityTest {

    @PersistenceContext
    private EntityManager em;

    @Test
    @DisplayName("Verify all 11 JPA entities can be persisted and retrieved")
    void testAll11EntitiesPersistAndRetrieve() {
        // 1. User
        User user1 = User.builder()
                .username("tester1")
                .email("tester1@example.com")
                .passwordHash("hashedpass")
                .bio("Bio tester 1")
                .build();
        em.persist(user1);

        User user2 = User.builder()
                .username("tester2")
                .email("tester2@example.com")
                .passwordHash("hashedpass")
                .build();
        em.persist(user2);
        em.flush();

        assertNotNull(user1.getId());
        assertNotNull(user2.getId());
        assertFalse(user1.isPrivate());
        assertTrue(user1.isNotificationsEnabled());
        assertNotNull(user1.getCreatedAt());

        // 2. Media
        Media media1 = Media.builder()
                .userId(user1.getId())
                .type(MediaType.POST)
                .mediaKind(MediaKind.IMAGE)
                .r2Key("uploads/images/test1.jpg")
                .caption("Hello #world #travel")
                .build();
        em.persist(media1);
        em.flush();

        assertNotNull(media1.getId());
        assertEquals(0, media1.getLikeCount());
        assertEquals(0, media1.getCommentCount());
        assertEquals(0, media1.getShareCount());
        assertEquals(0, media1.getViewCount());
        assertNotNull(media1.getCreatedAt());

        // 3. MediaTag
        MediaTag tag1 = MediaTag.builder()
                .mediaId(media1.getId())
                .tag("world")
                .build();
        MediaTag tag2 = MediaTag.builder()
                .mediaId(media1.getId())
                .tag("travel")
                .build();
        em.persist(tag1);
        em.persist(tag2);
        em.flush();

        MediaTag foundTag = em.find(MediaTag.class, new MediaTagId(media1.getId(), "world"));
        assertNotNull(foundTag);

        // 4. Like
        Like like1 = Like.builder()
                .userId(user2.getId())
                .mediaId(media1.getId())
                .build();
        em.persist(like1);
        em.flush();

        Like foundLike = em.find(Like.class, new LikeId(user2.getId(), media1.getId()));
        assertNotNull(foundLike);
        assertNotNull(foundLike.getCreatedAt());

        // 5. Comment
        Comment comment1 = Comment.builder()
                .userId(user2.getId())
                .mediaId(media1.getId())
                .text("Awesome picture!")
                .build();
        em.persist(comment1);
        em.flush();

        assertNotNull(comment1.getId());
        assertEquals("Awesome picture!", comment1.getText());
        assertNotNull(comment1.getCreatedAt());

        // 6. Follow
        Follow follow1 = Follow.builder()
                .followerId(user2.getId())
                .followingId(user1.getId())
                .build();
        em.persist(follow1);
        em.flush();

        Follow foundFollow = em.find(Follow.class, new FollowId(user2.getId(), user1.getId()));
        assertNotNull(foundFollow);

        // 7. FollowRequest
        FollowRequest req1 = FollowRequest.builder()
                .requesterId(user1.getId())
                .targetId(user2.getId())
                .build();
        em.persist(req1);
        em.flush();

        FollowRequest foundReq = em.find(FollowRequest.class, new FollowRequestId(user1.getId(), user2.getId()));
        assertNotNull(foundReq);

        // 8. StoryView
        Media story = Media.builder()
                .userId(user1.getId())
                .type(MediaType.STORY)
                .mediaKind(MediaKind.IMAGE)
                .r2Key("uploads/stories/s1.jpg")
                .expiresAt(Instant.now().plusSeconds(86400))
                .build();
        em.persist(story);
        em.flush();

        StoryView storyView = StoryView.builder()
                .userId(user2.getId())
                .mediaId(story.getId())
                .build();
        em.persist(storyView);
        em.flush();

        StoryView foundStoryView = em.find(StoryView.class, new StoryViewId(user2.getId(), story.getId()));
        assertNotNull(foundStoryView);

        // 9. MediaView
        MediaView mediaView = MediaView.builder()
                .userId(user2.getId())
                .mediaId(media1.getId())
                .watchMs(15000L)
                .durationMs(30000L)
                .completed(false)
                .build();
        em.persist(mediaView);
        em.flush();

        assertNotNull(mediaView.getId());
        assertEquals(15000L, mediaView.getWatchMs());
        assertNotNull(mediaView.getViewedAt());

        // 10. Share
        Share share = Share.builder()
                .userId(user2.getId())
                .mediaId(media1.getId())
                .build();
        em.persist(share);
        em.flush();

        assertNotNull(share.getId());
        assertNotNull(share.getCreatedAt());

        // 11. UserInterest
        UserInterest interest = UserInterest.builder()
                .userId(user2.getId())
                .tag("travel")
                .score(1.5)
                .build();
        em.persist(interest);
        em.flush();

        UserInterest foundInterest = em.find(UserInterest.class, new UserInterestId(user2.getId(), "travel"));
        assertNotNull(foundInterest);
        assertEquals(1.5, foundInterest.getScore());
    }

    @Test
    @DisplayName("Verify duplicate composite PK in likes throws DataIntegrityViolationException")
    void testDuplicateLikeFails() {
        User u = User.builder().username("l_user").email("l_user@test.com").passwordHash("pwd").build();
        em.persist(u);
        Media m = Media.builder().userId(u.getId()).type(MediaType.POST).mediaKind(MediaKind.IMAGE).r2Key("k").build();
        em.persist(m);
        em.flush();

        Like l1 = Like.builder().userId(u.getId()).mediaId(m.getId()).build();
        em.persist(l1);
        em.flush();

        Like l2 = Like.builder().userId(u.getId()).mediaId(m.getId()).build();
        assertThrows(Exception.class, () -> {
            em.persist(l2);
            em.flush();
        });
    }

    @Test
    @DisplayName("Verify follow check constraint: self-follow fails in database")
    void testSelfFollowFails() {
        User u = User.builder().username("self_user").email("self@test.com").passwordHash("pwd").build();
        em.persist(u);
        em.flush();

        Follow selfFollow = Follow.builder().followerId(u.getId()).followingId(u.getId()).build();
        assertThrows(Exception.class, () -> {
            em.persist(selfFollow);
            em.flush();
        });
    }

    @Test
    @DisplayName("Verify follow_request check constraint: self-request fails in database")
    void testSelfFollowRequestFails() {
        User u = User.builder().username("self_req_user").email("self_req@test.com").passwordHash("pwd").build();
        em.persist(u);
        em.flush();

        FollowRequest selfReq = FollowRequest.builder().requesterId(u.getId()).targetId(u.getId()).build();
        assertThrows(Exception.class, () -> {
            em.persist(selfReq);
            em.flush();
        });
    }

    @Test
    @DisplayName("Verify ON DELETE CASCADE deletes child records when media is deleted")
    void testMediaCascadeDelete() {
        User u = User.builder().username("media_owner").email("m_owner@test.com").passwordHash("pwd").build();
        em.persist(u);
        Media m = Media.builder().userId(u.getId()).type(MediaType.POST).mediaKind(MediaKind.IMAGE).r2Key("k").build();
        em.persist(m);
        em.flush();

        Long mediaId = m.getId();

        // Add children
        em.persist(MediaTag.builder().mediaId(mediaId).tag("cascade_tag").build());
        em.persist(Like.builder().userId(u.getId()).mediaId(mediaId).build());
        em.persist(Comment.builder().userId(u.getId()).mediaId(mediaId).text("test comment").build());
        em.persist(StoryView.builder().userId(u.getId()).mediaId(mediaId).build());
        em.persist(MediaView.builder().userId(u.getId()).mediaId(mediaId).watchMs(100).durationMs(200).build());
        em.persist(Share.builder().userId(u.getId()).mediaId(mediaId).build());
        em.flush();

        // Delete media via native SQL to trigger DB CASCADE
        int deleted = em.createNativeQuery("DELETE FROM media WHERE id = :id")
                .setParameter("id", mediaId)
                .executeUpdate();
        assertEquals(1, deleted);
        em.flush();
        em.clear();

        // Verify child records cascaded
        List<?> tags = em.createNativeQuery("SELECT * FROM media_tags WHERE media_id = :id")
                .setParameter("id", mediaId).getResultList();
        assertTrue(tags.isEmpty(), "Media tags should be cascade deleted");

        List<?> likes = em.createNativeQuery("SELECT * FROM likes WHERE media_id = :id")
                .setParameter("id", mediaId).getResultList();
        assertTrue(likes.isEmpty(), "Likes should be cascade deleted");

        List<?> comments = em.createNativeQuery("SELECT * FROM comments WHERE media_id = :id")
                .setParameter("id", mediaId).getResultList();
        assertTrue(comments.isEmpty(), "Comments should be cascade deleted");

        List<?> storyViews = em.createNativeQuery("SELECT * FROM story_views WHERE media_id = :id")
                .setParameter("id", mediaId).getResultList();
        assertTrue(storyViews.isEmpty(), "Story views should be cascade deleted");

        List<?> mediaViews = em.createNativeQuery("SELECT * FROM media_views WHERE media_id = :id")
                .setParameter("id", mediaId).getResultList();
        assertTrue(mediaViews.isEmpty(), "Media views should be cascade deleted");

        List<?> shares = em.createNativeQuery("SELECT * FROM shares WHERE media_id = :id")
                .setParameter("id", mediaId).getResultList();
        assertTrue(shares.isEmpty(), "Shares should be cascade deleted");
    }

    @Test
    @DisplayName("Verify ON DELETE CASCADE deletes all user records when user is deleted")
    void testUserCascadeDelete() {
        User u1 = User.builder().username("casc_u1").email("c1@test.com").passwordHash("pwd").build();
        User u2 = User.builder().username("casc_u2").email("c2@test.com").passwordHash("pwd").build();
        em.persist(u1);
        em.persist(u2);
        em.flush();

        Long u1Id = u1.getId();
        Long u2Id = u2.getId();

        Media m = Media.builder().userId(u1Id).type(MediaType.POST).mediaKind(MediaKind.IMAGE).r2Key("k").build();
        em.persist(m);
        em.flush();
        Long mediaId = m.getId();

        em.persist(Follow.builder().followerId(u1Id).followingId(u2Id).build());
        em.persist(FollowRequest.builder().requesterId(u2Id).targetId(u1Id).build());
        em.persist(UserInterest.builder().userId(u1Id).tag("coding").score(2.0).build());
        em.persist(Like.builder().userId(u1Id).mediaId(mediaId).build());
        em.flush();

        // Delete user1 via native query
        int deleted = em.createNativeQuery("DELETE FROM users WHERE id = :id")
                .setParameter("id", u1Id)
                .executeUpdate();
        assertEquals(1, deleted);
        em.flush();
        em.clear();

        // Verify media deleted
        List<?> mediaList = em.createNativeQuery("SELECT * FROM media WHERE user_id = :id")
                .setParameter("id", u1Id).getResultList();
        assertTrue(mediaList.isEmpty(), "Media of deleted user should be cascade deleted");

        // Verify follows deleted
        List<?> follows = em.createNativeQuery("SELECT * FROM follows WHERE follower_id = :id OR following_id = :id")
                .setParameter("id", u1Id).getResultList();
        assertTrue(follows.isEmpty(), "Follows of deleted user should be cascade deleted");

        // Verify follow requests deleted
        List<?> requests = em.createNativeQuery("SELECT * FROM follow_requests WHERE requester_id = :id OR target_id = :id")
                .setParameter("id", u1Id).getResultList();
        assertTrue(requests.isEmpty(), "Follow requests of deleted user should be cascade deleted");

        // Verify user interests deleted
        List<?> interests = em.createNativeQuery("SELECT * FROM user_interests WHERE user_id = :id")
                .setParameter("id", u1Id).getResultList();
        assertTrue(interests.isEmpty(), "User interests of deleted user should be cascade deleted");
    }
}
