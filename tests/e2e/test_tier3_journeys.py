"""
Tier 3: Cross-Feature User Journeys (Pairwise & Workflow Interactions)
Validates state propagation across multiple subsystems in end-to-end user workflows.
"""

import os
import unittest

from tests.e2e.helpers import (
    create_test_user,
    generate_unique_suffix,
    upload_media_helper,
)
from tests.e2e.test_client import ApiClient


class TestTier3Journeys(unittest.TestCase):
    """Tier 3 Cross-Feature User Journeys Verification Suite."""

    @classmethod
    def setUpClass(cls):
        cls.base_url = os.environ.get("BASE_URL", "http://localhost:8080/api")

    def test_journey_01_full_social_content_lifecycle(self):
        """
        Journey 1: Full Social Lifecycle
        Signup -> Profile Update -> Post Upload -> Follow -> Feed Check ->
        Like -> Comment -> Share -> Unfollow -> Feed Removal -> Delete Post
        """
        # 1. Creator Signup & Profile Update
        creator, creator_data, _ = create_test_user(self.base_url, prefix="t3_j1_c")
        creator.update_profile(bio="Photographer and outdoor explorer")

        # 2. Upload Post
        _, post_card = upload_media_helper(
            creator, upload_type="POST", caption="Morning hike in the mountains #hiking #nature"
        )
        post_id = post_card["id"]

        # 3. Follower Signup
        follower, follower_data, _ = create_test_user(self.base_url, prefix="t3_j1_f")

        # Before follow: follower feed is empty
        empty_feed = follower.get_feed(page=0, size=10).data.get("items", [])
        self.assertNotIn(post_id, [m["id"] for m in empty_feed])

        # 4. Follow Creator
        follow_resp = follower.follow_user(creator_data["id"])
        follow_resp.assert_ok()
        self.assertTrue(follow_resp.data.get("following"))

        # 5. Follower Feed Check
        feed_after_follow = follower.get_feed(page=0, size=10).data.get("items", [])
        self.assertIn(post_id, [m["id"] for m in feed_after_follow])

        # 6. Like Post
        like_resp = follower.like_media(post_id)
        like_resp.assert_ok()
        self.assertTrue(like_resp.data.get("liked"))

        # 7. Add Comment
        comment_resp = follower.add_comment(post_id, "Incredible view!")
        comment_resp.assert_created()
        comment_id = comment_resp.data["id"]

        # 8. Share Post
        share_resp = follower.share_media(post_id)
        share_resp.assert_ok()

        # 9. Creator verifies engagement counters
        detail = creator.get_media(post_id).data
        self.assertEqual(detail.get("likeCount"), 1)
        self.assertEqual(detail.get("commentCount"), 1)
        self.assertEqual(detail.get("shareCount"), 1)

        # 10. Unfollow Creator
        unfollow_resp = follower.unfollow_user(creator_data["id"])
        unfollow_resp.assert_ok()

        # 11. Feed verification: post disappears from follower feed
        feed_after_unfollow = follower.get_feed(page=0, size=10).data.get("items", [])
        self.assertNotIn(post_id, [m["id"] for m in feed_after_unfollow])

        # 12. Creator deletes post
        del_resp = creator.delete_media(post_id)
        del_resp.assert_no_content()

        # 13. Verify post returns 404
        post_404 = creator.get_media(post_id)
        post_404.assert_error(404)

    def test_journey_02_private_account_request_and_approval_flow(self):
        """
        Journey 2: Private Account Privacy & Follow Request Lifecycle
        Private account -> Denied access (403) -> Request to follow ->
        Inbound request list -> Accept request -> Granted access -> Unfollow -> Revocation
        """
        # 1. Private creator
        creator, creator_data, _ = create_test_user(self.base_url, is_private=True, prefix="t3_j2_c")
        _, post_card = upload_media_helper(creator, upload_type="POST", caption="Private post")
        post_id = post_card["id"]

        # 2. Stranger attempts unauthorized access
        stranger, stranger_data, _ = create_test_user(self.base_url, prefix="t3_j2_s")

        # Media detail 403
        stranger.get_media(post_id).assert_error(403)

        # Media grid 403
        stranger.get_user_posts(creator_data["id"]).assert_error(403)

        # Profile canView false
        prof = stranger.get_user_profile(creator_data["id"]).data
        self.assertFalse(prof.get("canView"))

        # 3. Stranger sends follow request
        req_resp = stranger.follow_user(creator_data["id"])
        req_resp.assert_ok()
        self.assertFalse(req_resp.data.get("following"))
        self.assertTrue(req_resp.data.get("requested"))

        # 4. Creator lists inbound follow requests
        inbound = creator.get_follow_requests().data.get("items", [])
        self.assertIn(stranger_data["id"], [u["id"] for u in inbound])

        # 5. Creator accepts request
        acc_resp = creator.accept_follow_request(stranger_data["id"])
        acc_resp.assert_no_content()

        # 6. Stranger now has access
        prof_after = stranger.get_user_profile(creator_data["id"]).data
        self.assertTrue(prof_after.get("canView"))
        self.assertTrue(prof_after.get("followedByMe"))

        # Can now access post
        post_detail = stranger.get_media(post_id)
        post_detail.assert_ok()

        # Can view media grid
        grid = stranger.get_user_posts(creator_data["id"])
        grid.assert_ok()
        self.assertIn(post_id, [m["id"] for m in grid.data.get("items", [])])

        # Feed contains post
        feed = stranger.get_feed(page=0, size=10)
        feed.assert_ok()
        self.assertIn(post_id, [m["id"] for m in feed.data.get("items", [])])

        # 7. Stranger unfollows -> immediate revocation
        stranger.unfollow_user(creator_data["id"]).assert_ok()
        stranger.get_media(post_id).assert_error(403)

    def test_journey_03_privacy_toggle_and_auto_accept_promotion(self):
        """
        Journey 3: Privacy Mode Toggle & Pending Request Auto-Accept Promotion
        Private user receives multiple requests -> Switches to public ->
        All pending requests auto-promoted to active follows -> Follower count updated
        """
        creator, creator_data, _ = create_test_user(self.base_url, is_private=True, prefix="t3_j3_c")
        requester1, req1_data, _ = create_test_user(self.base_url, prefix="t3_j3_r1")
        requester2, req2_data, _ = create_test_user(self.base_url, prefix="t3_j3_r2")

        # Send follow requests
        requester1.follow_user(creator_data["id"]).assert_ok()
        requester2.follow_user(creator_data["id"]).assert_ok()

        # Verify 2 pending requests
        inbound = creator.get_follow_requests().data.get("items", [])
        self.assertEqual(len(inbound), 2)

        # Switch to public
        creator.update_settings(is_private=False, notifications_enabled=True).assert_ok()

        # Pending requests list is now empty
        inbound_after = creator.get_follow_requests().data.get("items", [])
        self.assertEqual(len(inbound_after), 0)

        # Both requesters are now active followers
        prof1 = requester1.get_user_profile(creator_data["id"]).data
        self.assertTrue(prof1.get("followedByMe"))

        prof2 = requester2.get_user_profile(creator_data["id"]).data
        self.assertTrue(prof2.get("followedByMe"))

        # Creator followerCount incremented by 2
        creator_prof = creator.get_user_profile(creator_data["id"]).data
        self.assertGreaterEqual(creator_prof.get("followerCount", 0), 2)

    def test_journey_04_reel_discovery_telemetry_and_exclude_cycle(self):
        """
        Journey 4: Reel Discovery, View Telemetry & Recommendation Feedback
        Upload Reel -> Discover in /reels -> Send watch telemetry ->
        Like & Comment -> Exclude parameter filtration
        """
        creator, _, _ = create_test_user(self.base_url, prefix="t3_j4_c")
        _, reel_card = upload_media_helper(
            creator, upload_type="REEL", content_type="video/mp4", caption="Daily workout #fitness #gym"
        )
        reel_id = reel_card["id"]

        viewer, _, _ = create_test_user(self.base_url, prefix="t3_j4_v")

        # 1. View telemetry event
        view_resp = viewer.record_view(reel_id, watch_ms=18000, duration_ms=18000, completed=True)
        view_resp.assert_no_content()

        # 2. Like & Comment
        viewer.like_media(reel_id).assert_ok()
        viewer.add_comment(reel_id, "Solid form!").assert_created()

        # 3. Query reels excluding this reel
        reels_resp = viewer.get_reels(size=5, exclude=str(reel_id))
        reels_resp.assert_ok()
        returned_ids = [r["id"] for r in reels_resp.data.get("items", [])]
        self.assertNotIn(reel_id, returned_ids)

    def test_journey_05_multi_story_sequential_viewing_and_seen_state(self):
        """
        Journey 5: Multi-Story Grouping, Sequential Viewing & Seen State Transition
        Creator uploads 2 stories -> Follower sees hasUnseen: true ->
        Follower marks 1 seen (still hasUnseen: true) -> Follower marks 2 seen (hasUnseen: false)
        """
        creator, creator_data, _ = create_test_user(self.base_url, prefix="t3_j5_c")
        _, s1 = upload_media_helper(creator, upload_type="STORY", caption="Morning coffee")
        _, s2 = upload_media_helper(creator, upload_type="STORY", caption="Afternoon snack")

        follower, _, _ = create_test_user(self.base_url, prefix="t3_j5_f")
        follower.follow_user(creator_data["id"]).assert_ok()

        # Step 1: Check initial stories feed
        st_resp1 = follower.get_stories()
        st_resp1.assert_ok()
        group1 = next((g for g in st_resp1.data.get("items", []) if g["user"]["id"] == creator_data["id"]), None)
        self.assertIsNotNone(group1)
        self.assertTrue(group1.get("hasUnseen"))

        # Step 2: Mark Story 1 seen
        follower.mark_story_seen(s1["id"]).assert_no_content()

        st_resp2 = follower.get_stories()
        group2 = next((g for g in st_resp2.data.get("items", []) if g["user"]["id"] == creator_data["id"]), None)
        self.assertIsNotNone(group2)
        # Still hasUnseen because Story 2 is not yet seen
        self.assertTrue(group2.get("hasUnseen"))

        # Step 3: Mark Story 2 seen
        follower.mark_story_seen(s2["id"]).assert_no_content()

        st_resp3 = follower.get_stories()
        group3 = next((g for g in st_resp3.data.get("items", []) if g["user"]["id"] == creator_data["id"]), None)
        self.assertIsNotNone(group3)
        # Fully seen now
        self.assertFalse(group3.get("hasUnseen"))

    def test_journey_06_social_discovery_to_engagement_workflow(self):
        """
        Journey 6: Suggested Users -> Profile Inspection -> Media Grid -> Engagement
        New user checks suggested -> Views profile -> Inspects posts grid -> Follows & Likes
        """
        user, _, _ = create_test_user(self.base_url, prefix="t3_j6_u")

        # 1. Suggested accounts
        sugg_resp = user.get_suggested_users()
        sugg_resp.assert_ok()
        items = sugg_resp.data.get("items", [])
        if items:
            target_id = items[0]["id"]

            # 2. Inspect profile
            prof_resp = user.get_user_profile(target_id)
            prof_resp.assert_ok()

            # 3. Inspect grid if allowed
            if prof_resp.data.get("canView"):
                grid_resp = user.get_user_posts(target_id, page=0, size=5)
                grid_resp.assert_ok()
                grid_items = grid_resp.data.get("items", [])
                if grid_items:
                    post_id = grid_items[0]["id"]
                    # 4. Like media
                    user.like_media(post_id).assert_ok()

            # 5. Follow target
            user.follow_user(target_id).assert_ok()


if __name__ == "__main__":
    unittest.main()
