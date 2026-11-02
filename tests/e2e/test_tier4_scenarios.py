"""
Tier 4: Real-World Application Scenarios
Simulates realistic multi-actor social media workloads: viral engagement bursts,
community moderation, private account management, creator portfolios, and recommendation adaptation.
"""

import os
import unittest

from tests.e2e.helpers import (
    create_test_user,
    upload_media_helper,
)
from tests.e2e.test_client import ApiClient


class TestTier4Scenarios(unittest.TestCase):
    """Tier 4 Real-World Multi-User Application Scenarios."""

    @classmethod
    def setUpClass(cls):
        cls.base_url = os.environ.get("BASE_URL", "http://localhost:8080/api")

    def test_scenario_01_multi_user_viral_post_event(self):
        """
        Scenario 1: Multi-User Viral Post Event
        Creator uploads post -> 5 users interact (like, comment, share, view telemetry) ->
        Verify atomic counter consistency (likes=5, comments=5, shares=3).
        """
        creator, _, _ = create_test_user(self.base_url, prefix="t4_sc1_c")
        _, post_card = upload_media_helper(
            creator, upload_type="POST", caption="Viral announcement! #breaking #news #viral"
        )
        post_id = post_card["id"]

        # Provision 5 distinct active users
        crowd = [create_test_user(self.base_url, prefix=f"t4_sc1_u{i}")[0] for i in range(5)]

        # 1. All 5 users like the post
        for user in crowd:
            user.like_media(post_id).assert_ok()

        # 2. All 5 users comment on the post
        for idx, user in enumerate(crowd):
            user.add_comment(post_id, f"Awesome news from user #{idx}!").assert_created()

        # 3. First 3 users share the post
        for user in crowd[:3]:
            user.share_media(post_id).assert_ok()

        # 4. All 5 users submit view telemetry
        for user in crowd:
            user.record_view(post_id, watch_ms=10000, duration_ms=10000, completed=True).assert_no_content()

        # 5. Verify atomic counter integrity from creator's perspective
        detail = creator.get_media(post_id).data
        self.assertEqual(detail.get("likeCount"), 5, "Like counter must equal 5")
        self.assertEqual(detail.get("commentCount"), 5, "Comment counter must equal 5")
        self.assertEqual(detail.get("shareCount"), 3, "Share counter must equal 3")
        self.assertFalse(detail.get("likedByMe"), "Creator did not like their own post")

        # 6. Verify likedByMe is True for crowd users
        user_0_detail = crowd[0].get_media(post_id).data
        self.assertTrue(user_0_detail.get("likedByMe"))

        # 7. Check comments pagination and ordering
        comments = creator.get_comments(post_id, page=0, size=10).data.get("items", [])
        self.assertEqual(len(comments), 5)

    def test_scenario_02_content_moderation_and_access_control(self):
        """
        Scenario 2: Content Moderation & Access Control Lifecycle
        Post owner moderation vs comment authors vs spectators trying forbidden actions.
        """
        moderator, _, _ = create_test_user(self.base_url, prefix="t4_sc2_mod")
        user_friendly, _, _ = create_test_user(self.base_url, prefix="t4_sc2_uf")
        user_troll, _, _ = create_test_user(self.base_url, prefix="t4_sc2_ut")
        spectator, _, _ = create_test_user(self.base_url, prefix="t4_sc2_sp")

        _, post = upload_media_helper(moderator, upload_type="POST", caption="Moderated community post")
        post_id = post["id"]

        # Comments added
        comm_good = user_friendly.add_comment(post_id, "Constructive discussion").data["id"]
        comm_bad = user_troll.add_comment(post_id, "Inappropriate trolling").data["id"]

        # Counter is 2
        self.assertEqual(moderator.get_media(post_id).data.get("commentCount"), 2)

        # 1. Spectator tries to delete troll comment -> blocked 403
        spectator.delete_comment(comm_bad).assert_error(403)

        # 2. Troll tries to delete post -> blocked 403
        user_troll.delete_media(post_id).assert_error(403)

        # 3. Moderator exercises owner moderation rights to remove troll comment -> 204
        moderator.delete_comment(comm_bad).assert_no_content()

        # 4. Friendly user deletes own comment -> 204
        user_friendly.delete_comment(comm_good).assert_no_content()

        # 5. Comment count accurately decremented to 0
        final_detail = moderator.get_media(post_id).data
        self.assertEqual(final_detail.get("commentCount"), 0)

    def test_scenario_03_private_community_and_selective_membership(self):
        """
        Scenario 3: Private Community & Follow Request Management
        Private VIP receives requests from A, B, C; accepts A, declines B, leaves C pending.
        Verifies visibility separation, then toggles public auto-accepting C.
        """
        vip, vip_data, _ = create_test_user(self.base_url, is_private=True, prefix="t4_sc3_vip")
        user_a, user_a_data, _ = create_test_user(self.base_url, prefix="t4_sc3_ua")
        user_b, user_b_data, _ = create_test_user(self.base_url, prefix="t4_sc3_ub")
        user_c, user_c_data, _ = create_test_user(self.base_url, prefix="t4_sc3_uc")

        _, post = upload_media_helper(vip, upload_type="POST", caption="VIP Exclusive")
        post_id = post["id"]

        # All 3 request access
        user_a.follow_user(vip_data["id"]).assert_ok()
        user_b.follow_user(vip_data["id"]).assert_ok()
        user_c.follow_user(vip_data["id"]).assert_ok()

        # VIP accepts A, declines B
        vip.accept_follow_request(user_a_data["id"]).assert_no_content()
        vip.decline_follow_request(user_b_data["id"]).assert_no_content()

        # Access check:
        # A has access
        user_a.get_media(post_id).assert_ok()
        self.assertTrue(user_a.get_user_profile(vip_data["id"]).data.get("canView"))

        # B is rejected
        user_b.get_media(post_id).assert_error(403)
        self.assertFalse(user_b.get_user_profile(vip_data["id"]).data.get("canView"))

        # C is pending (cannot view)
        user_c.get_media(post_id).assert_error(403)
        self.assertFalse(user_c.get_user_profile(vip_data["id"]).data.get("canView"))

        # VIP opens community (switches to public)
        vip.update_settings(is_private=False, notifications_enabled=True).assert_ok()

        # C now automatically has access
        user_c.get_media(post_id).assert_ok()
        self.assertTrue(user_c.get_user_profile(vip_data["id"]).data.get("canView"))

    def test_scenario_04_creator_portfolio_and_grid_pagination(self):
        """
        Scenario 4: Creator Media Portfolio & Grid Pagination Management
        Upload 4 Posts, 3 Reels, 2 Stories -> Verify grid pagination (size=5),
        story exclusion from grid, and postCount stats consistency.
        """
        creator, creator_data, _ = create_test_user(self.base_url, prefix="t4_sc4_cr")

        # 4 Posts
        for i in range(4):
            upload_media_helper(creator, upload_type="POST", caption=f"Post #{i} #portfolio")

        # 3 Reels
        for i in range(3):
            upload_media_helper(
                creator, upload_type="REEL", content_type="video/mp4", caption=f"Reel #{i} #reel"
            )

        # 2 Stories (must NOT appear in grid)
        for i in range(2):
            upload_media_helper(creator, upload_type="STORY", caption=f"Story #{i}")

        # Page 0 (size 5)
        p0_resp = creator.get_user_posts(creator_data["id"], page=0, size=5)
        p0_resp.assert_ok()
        p0_items = p0_resp.data.get("items", [])
        self.assertEqual(len(p0_items), 5)
        self.assertTrue(p0_resp.data.get("hasNext"))

        # Page 1 (size 5)
        p1_resp = creator.get_user_posts(creator_data["id"], page=1, size=5)
        p1_resp.assert_ok()
        p1_items = p1_resp.data.get("items", [])
        self.assertEqual(len(p1_items), 2, "Page 1 should have remaining 2 items (total 7)")
        self.assertFalse(p1_resp.data.get("hasNext"))

        # Verify no item in grid has type STORY
        all_grid_items = p0_items + p1_items
        for item in all_grid_items:
            self.assertIn(item.get("type"), ("POST", "REEL"), "Grid must contain only POST and REEL")

        # Profile postCount should equal 7
        profile = creator.get_user_profile(creator_data["id"]).data
        self.assertEqual(profile.get("postCount"), 7)

    def test_scenario_05_multi_user_recommendation_and_telemetry(self):
        """
        Scenario 5: Multi-User Recommendation & Tag Interest Telemetry
        Multiple creators and viewers simulating watch and engagement telemetry.
        """
        creator1, _, _ = create_test_user(self.base_url, prefix="t4_sc5_c1")
        _, r1 = upload_media_helper(
            creator1, upload_type="REEL", content_type="video/mp4", caption="Intense CrossFit #fitness #crossfit"
        )

        creator2, _, _ = create_test_user(self.base_url, prefix="t4_sc5_c2")
        _, r2 = upload_media_helper(
            creator2, upload_type="REEL", content_type="video/mp4", caption="Top 10 RPG games #gaming #rpg"
        )

        viewer, _, _ = create_test_user(self.base_url, prefix="t4_sc5_vw")

        # Viewer watches r1 with completion
        viewer.record_view(r1["id"], watch_ms=20000, duration_ms=20000, completed=True).assert_no_content()
        viewer.like_media(r1["id"]).assert_ok()

        # Viewer watches r2 briefly (skipped)
        viewer.record_view(r2["id"], watch_ms=1000, duration_ms=20000, completed=False).assert_no_content()

        # Recommendation feed returns candidate reels
        reels_resp = viewer.get_reels(size=5)
        reels_resp.assert_ok()
        self.assertIsInstance(reels_resp.data.get("items"), list)


if __name__ == "__main__":
    unittest.main()
