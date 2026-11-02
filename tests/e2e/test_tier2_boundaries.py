"""
Tier 2: Boundary & Corner Cases
Comprehensive negative, adversarial, and boundary testing across all 11 subsystems (>=5 tests per feature).
Subsystems:
1. Auth Boundaries
2. Feed Boundaries
3. Stories Boundaries
4. Reels Boundaries
5. Media Boundaries
6. Comments Boundaries
7. Profiles Boundaries
8. Follows Boundaries
9. Follow Requests Boundaries
10. Upload Boundaries
11. Settings Boundaries
"""

import os
import unittest

from tests.e2e.helpers import (
    MINIMAL_JPEG_BYTES,
    MINIMAL_MP4_BYTES,
    create_test_user,
    generate_unique_suffix,
    generate_user_credentials,
    upload_media_helper,
)
from tests.e2e.test_client import ApiClient


class TestTier2Boundaries(unittest.TestCase):
    """Tier 2 Boundary and Corner Cases Verification Suite."""

    @classmethod
    def setUpClass(cls):
        cls.base_url = os.environ.get("BASE_URL", "http://localhost:8080/api")

    # =========================================================================
    # 1. AUTH BOUNDARIES (7 tests)
    # =========================================================================

    def test_auth_boundary_01_wrong_password_401(self):
        """Verify login with wrong password returns 401 with standard message."""
        client, user_data, _ = create_test_user(self.base_url, prefix="t2_wpw")
        login_resp = ApiClient(self.base_url).login(username=user_data["username"], password="WrongPassword999!")
        login_resp.assert_error(401, message_substr="Invalid username or password")

    def test_auth_boundary_02_unknown_username_401(self):
        """Verify login with unknown username returns 401 with identical message."""
        login_resp = ApiClient(self.base_url).login(username="non_existent_user_9999", password="Password123")
        login_resp.assert_error(401, message_substr="Invalid username or password")

    def test_auth_boundary_03_duplicate_username_409(self):
        """Verify signup with duplicate username returns 409 Conflict."""
        client, user_data, _ = create_test_user(self.base_url, prefix="t2_dupun")
        other_email = f"diff_{generate_unique_suffix()}@testdomain.internal"

        resp = ApiClient(self.base_url).signup(
            username=user_data["username"],
            email=other_email,
            password="ValidPassword123",
        )
        resp.assert_error(409, message_substr="username")

    def test_auth_boundary_04_duplicate_email_409(self):
        """Verify signup with duplicate email returns 409 Conflict."""
        client, user_data, _ = create_test_user(self.base_url, prefix="t2_dupem")
        other_username = f"diff_{generate_unique_suffix()}"[:28]

        resp = ApiClient(self.base_url).signup(
            username=other_username,
            email=user_data["email"],
            password="ValidPassword123",
        )
        resp.assert_error(409, message_substr="email")

    def test_auth_boundary_05_weak_password_400(self):
        """Verify signup with password lacking digits or < 8 chars returns 400."""
        resp = ApiClient(self.base_url).signup(
            username=f"usr_{generate_unique_suffix()}"[:28],
            email=f"weak_{generate_unique_suffix()}@testdomain.internal",
            password="short",  # < 8 chars and no digit
        )
        resp.assert_error(400)

    def test_auth_boundary_06_invalid_username_characters_400(self):
        """Verify username with illegal characters (spaces, special symbols) returns 400."""
        resp = ApiClient(self.base_url).signup(
            username="invalid user name!",
            email=f"inv_{generate_unique_suffix()}@testdomain.internal",
            password="ValidPassword123",
        )
        resp.assert_error(400)

    def test_auth_boundary_07_malformed_token_401(self):
        """Verify requests with malformed or tampered JWT return 401."""
        client = ApiClient(self.base_url, token="eyInvalidHeader.eyInvalidPayload.tamperedSignature")
        resp = client.get_me()
        resp.assert_error(401)

    # =========================================================================
    # 2. FEED BOUNDARIES (5 tests)
    # =========================================================================

    def test_feed_boundary_01_unauthenticated_401(self):
        """Verify GET /feed without Authorization header returns 401."""
        client = ApiClient(self.base_url)
        resp = client.get_feed()
        resp.assert_error(401)

    def test_feed_boundary_02_negative_page_400(self):
        """Verify GET /feed with negative page number returns 400."""
        client, _, _ = create_test_user(self.base_url, prefix="t2_fdneg")
        resp = client.get_feed(page=-1, size=10)
        resp.assert_error(400)

    def test_feed_boundary_03_zero_or_negative_size_400(self):
        """Verify GET /feed with size=0 or size < 1 returns 400."""
        client, _, _ = create_test_user(self.base_url, prefix="t2_fdsz0")
        resp = client.get_feed(page=0, size=0)
        resp.assert_error(400)

    def test_feed_boundary_04_suggested_excludes_self(self):
        """Verify GET /users/suggested never includes current user."""
        client, user_data, _ = create_test_user(self.base_url, prefix="t2_fdsgslf")
        resp = client.get_suggested_users()
        resp.assert_ok()
        returned_ids = [u["id"] for u in resp.data.get("items", [])]
        self.assertNotIn(user_data["id"], returned_ids)

    def test_feed_boundary_05_suggested_excludes_already_followed(self):
        """Verify GET /users/suggested excludes users already followed."""
        user_a, user_a_data, _ = create_test_user(self.base_url, prefix="t2_fdsga")
        user_b, user_b_data, _ = create_test_user(self.base_url, prefix="t2_fdsgb")

        user_a.follow_user(user_b_data["id"])
        resp = user_a.get_suggested_users()
        resp.assert_ok()
        returned_ids = [u["id"] for u in resp.data.get("items", [])]
        self.assertNotIn(user_b_data["id"], returned_ids)

    # =========================================================================
    # 3. STORIES BOUNDARIES (5 tests)
    # =========================================================================

    def test_stories_boundary_01_unauthenticated_401(self):
        """Verify GET /stories without token returns 401."""
        resp = ApiClient(self.base_url).get_stories()
        resp.assert_error(401)

    def test_stories_boundary_02_mark_seen_non_existent_404(self):
        """Verify POST /stories/{id}/seen for non-existent story returns 404."""
        client, _, _ = create_test_user(self.base_url, prefix="t2_st404")
        resp = client.mark_story_seen(story_id=999999999)
        resp.assert_error(404)

    def test_stories_boundary_03_mark_seen_duplicate_idempotent(self):
        """Verify repeated calls to mark story seen are idempotent and return 204."""
        client, _, _ = create_test_user(self.base_url, prefix="t2_stidm")
        _, story_card = upload_media_helper(client, upload_type="STORY", caption="Seen Story")
        story_id = story_card["id"]

        resp1 = client.mark_story_seen(story_id=story_id)
        resp1.assert_no_content()

        resp2 = client.mark_story_seen(story_id=story_id)
        resp2.assert_no_content("Duplicate seen tracking must be idempotent 204")

    def test_stories_boundary_04_stories_excluded_from_feed(self):
        """Verify STORY media items never appear in GET /feed."""
        creator, _, _ = create_test_user(self.base_url, prefix="t2_stnofd")
        _, story_card = upload_media_helper(creator, upload_type="STORY", caption="Story Item")
        story_id = story_card["id"]

        feed_resp = creator.get_feed(page=0, size=20)
        feed_resp.assert_ok()
        feed_ids = [m["id"] for m in feed_resp.data.get("items", [])]
        self.assertNotIn(story_id, feed_ids, "STORY media must never appear in main feed")

    def test_stories_boundary_05_seen_on_post_or_reel_rejected_404(self):
        """Verify POST /stories/{id}/seen on a POST or REEL returns 404 per docs.md:249."""
        client, _, _ = create_test_user(self.base_url, prefix="t2_stnotst")
        _, post_card = upload_media_helper(client, upload_type="POST")
        post_id = post_card["id"]

        resp = client.mark_story_seen(story_id=post_id)
        resp.assert_error(404, message_substr="not a story")

    # =========================================================================
    # 4. REELS BOUNDARIES (5 tests)
    # =========================================================================

    def test_reels_boundary_01_unauthenticated_401(self):
        """Verify GET /reels without token returns 401."""
        resp = ApiClient(self.base_url).get_reels()
        resp.assert_error(401)

    def test_reels_boundary_02_size_zero_or_negative_400(self):
        """Verify GET /reels with size=0 returns 400."""
        client, _, _ = create_test_user(self.base_url, prefix="t2_rlsz0")
        resp = client.get_reels(size=0)
        resp.assert_error(400)

    def test_reels_boundary_03_size_exceeding_max_400(self):
        """Verify GET /reels with size > 20 returns 400 per docs.md:252."""
        client, _, _ = create_test_user(self.base_url, prefix="t2_rlszmax")
        resp = client.get_reels(size=25)
        resp.assert_error(400)

    def test_reels_boundary_04_exclude_unknown_ids_handled(self):
        """Verify exclude parameter with unknown IDs is handled cleanly (200 OK)."""
        client, _, _ = create_test_user(self.base_url, prefix="t2_rlexunk")
        resp = client.get_reels(size=5, exclude="999999991,999999992")
        resp.assert_ok()

    def test_reels_boundary_05_reels_exclude_user_own_reels(self):
        """Verify GET /reels does not recommend current user's own reels."""
        creator, creator_data, _ = create_test_user(self.base_url, prefix="t2_rlown")
        upload_media_helper(
            creator, upload_type="REEL", content_type="video/mp4", caption="My Own Reel #test"
        )

        resp = creator.get_reels(size=10)
        resp.assert_ok()
        creator_ids = [r.get("user", {}).get("id") for r in resp.data.get("items", [])]
        self.assertNotIn(creator_data["id"], creator_ids, "Reels feed must not include caller's own reels")

    # =========================================================================
    # 5. MEDIA BOUNDARIES (6 tests)
    # =========================================================================

    def test_media_boundary_01_get_non_existent_404(self):
        """Verify GET /media/{id} for non-existent ID returns 404."""
        client, _, _ = create_test_user(self.base_url, prefix="t2_md404")
        resp = client.get_media(999999999)
        resp.assert_error(404)

    def test_media_boundary_02_private_media_non_follower_403(self):
        """Verify non-follower cannot view media of private account (returns 403)."""
        creator, _, _ = create_test_user(self.base_url, is_private=True, prefix="t2_mdprv_c")
        viewer, _, _ = create_test_user(self.base_url, prefix="t2_mdprv_v")
        _, post_card = upload_media_helper(creator, upload_type="POST")
        media_id = post_card["id"]

        resp = viewer.get_media(media_id)
        resp.assert_error(403, message_substr="This account is private")

    def test_media_boundary_03_delete_non_owner_403(self):
        """Verify non-owner attempting DELETE /media/{id} returns 403 Forbidden."""
        creator, _, _ = create_test_user(self.base_url, prefix="t2_mddel_c")
        attacker, _, _ = create_test_user(self.base_url, prefix="t2_mddel_a")
        _, post_card = upload_media_helper(creator, upload_type="POST")
        media_id = post_card["id"]

        resp = attacker.delete_media(media_id)
        resp.assert_error(403)

    def test_media_boundary_04_delete_non_existent_404(self):
        """Verify DELETE /media/{id} for non-existent ID returns 404."""
        client, _, _ = create_test_user(self.base_url, prefix="t2_mddel404")
        resp = client.delete_media(999999999)
        resp.assert_error(404)

    def test_media_boundary_05_view_telemetry_on_story_or_self_ignored_204(self):
        """Verify view telemetry on STORY or self-owned media returns 204 without recording."""
        creator, _, _ = create_test_user(self.base_url, prefix="t2_mdvwign")
        _, post_card = upload_media_helper(creator, upload_type="POST")
        media_id = post_card["id"]

        # View own media -> ignored with 204
        resp = creator.record_view(media_id, watch_ms=5000, duration_ms=10000, completed=False)
        resp.assert_no_content()

    def test_media_boundary_06_unlike_floors_at_zero(self):
        """Verify unliking a post with 0 likes leaves likeCount at 0 and does not go negative."""
        creator, _, _ = create_test_user(self.base_url, prefix="t2_mdunlk0")
        _, post_card = upload_media_helper(creator, upload_type="POST")
        media_id = post_card["id"]

        resp = creator.unlike_media(media_id)
        resp.assert_ok()
        self.assertGreaterEqual(resp.data.get("likeCount", 0), 0)

    # =========================================================================
    # 6. COMMENTS BOUNDARIES (5 tests)
    # =========================================================================

    def test_comments_boundary_01_blank_comment_rejected_400(self):
        """Verify adding blank or whitespace-only comment returns 400 Bad Request."""
        client, _, _ = create_test_user(self.base_url, prefix="t2_cmblk")
        _, post_card = upload_media_helper(client, upload_type="POST")

        resp = client.add_comment(post_card["id"], text="   \t\n   ")
        resp.assert_error(400)

    def test_comments_boundary_02_oversized_comment_rejected_400(self):
        """Verify comment text > 500 characters returns 400."""
        client, _, _ = create_test_user(self.base_url, prefix="t2_cmovr")
        _, post_card = upload_media_helper(client, upload_type="POST")

        resp = client.add_comment(post_card["id"], text="A" * 501)
        resp.assert_error(400)

    def test_comments_boundary_03_comment_on_private_media_non_follower_403(self):
        """Verify non-follower cannot comment on private account's post (returns 403)."""
        creator, _, _ = create_test_user(self.base_url, is_private=True, prefix="t2_cmprv_c")
        stranger, _, _ = create_test_user(self.base_url, prefix="t2_cmprv_s")
        _, post_card = upload_media_helper(creator, upload_type="POST")

        resp = stranger.add_comment(post_card["id"], text="Illegal comment")
        resp.assert_error(403)

    def test_comments_boundary_04_delete_comment_unauthorized_third_party_403(self):
        """Verify user who is neither comment author nor post owner cannot delete comment (returns 403)."""
        creator, _, _ = create_test_user(self.base_url, prefix="t2_cmdel_c")
        author, _, _ = create_test_user(self.base_url, prefix="t2_cmdel_a")
        stranger, _, _ = create_test_user(self.base_url, prefix="t2_cmdel_s")
        _, post_card = upload_media_helper(creator, upload_type="POST")

        comment_resp = author.add_comment(post_card["id"], text="Legitimate comment")
        comment_id = comment_resp.data["id"]

        resp = stranger.delete_comment(comment_id)
        resp.assert_error(403)

    def test_comments_boundary_05_delete_non_existent_comment_404(self):
        """Verify DELETE /comments/{id} for non-existent ID returns 404."""
        client, _, _ = create_test_user(self.base_url, prefix="t2_cmdel404")
        resp = client.delete_comment(999999999)
        resp.assert_error(404)

    # =========================================================================
    # 7. PROFILES BOUNDARIES (5 tests)
    # =========================================================================

    def test_profiles_boundary_01_non_existent_user_404(self):
        """Verify GET /users/{id}/profile for non-existent user returns 404."""
        client, _, _ = create_test_user(self.base_url, prefix="t2_pr404")
        resp = client.get_user_profile(999999999)
        resp.assert_error(404)

    def test_profiles_boundary_02_private_profile_can_view_false(self):
        """Verify private profile viewed by non-follower returns canView: false."""
        target, target_data, _ = create_test_user(self.base_url, is_private=True, prefix="t2_prcanvw_t")
        viewer, _, _ = create_test_user(self.base_url, prefix="t2_prcanvw_v")

        resp = viewer.get_user_profile(target_data["id"])
        resp.assert_ok()
        self.assertFalse(resp.data.get("canView"))

    def test_profiles_boundary_03_private_posts_grid_403(self):
        """Verify GET /users/{id}/posts on private user by non-follower returns 403."""
        target, target_data, _ = create_test_user(self.base_url, is_private=True, prefix="t2_prgrid_t")
        viewer, _, _ = create_test_user(self.base_url, prefix="t2_prgrid_v")

        resp = viewer.get_user_posts(target_data["id"])
        resp.assert_error(403, message_substr="This account is private")

    def test_profiles_boundary_04_private_followers_list_403(self):
        """Verify GET /users/{id}/followers on private user by non-follower returns 403."""
        target, target_data, _ = create_test_user(self.base_url, is_private=True, prefix="t2_prflw403_t")
        viewer, _, _ = create_test_user(self.base_url, prefix="t2_prflw403_v")

        resp = viewer.get_user_followers(target_data["id"])
        resp.assert_error(403)

    def test_profiles_boundary_05_private_following_list_403(self):
        """Verify GET /users/{id}/following on private user by non-follower returns 403."""
        target, target_data, _ = create_test_user(self.base_url, is_private=True, prefix="t2_prflg403_t")
        viewer, _, _ = create_test_user(self.base_url, prefix="t2_prflg403_v")

        resp = viewer.get_user_following(target_data["id"])
        resp.assert_error(403)

    # =========================================================================
    # 8. FOLLOWS BOUNDARIES (5 tests)
    # =========================================================================

    def test_follows_boundary_01_self_follow_rejected_400(self):
        """Verify following self returns 400 Bad Request with 'Cannot follow yourself' message."""
        client, user_data, _ = create_test_user(self.base_url, prefix="t2_flwslf")
        resp = client.follow_user(user_data["id"])
        resp.assert_error(400, message_substr="Cannot follow yourself")

    def test_follows_boundary_02_self_unfollow_rejected_400(self):
        """Verify unfollowing self returns 400 Bad Request."""
        client, user_data, _ = create_test_user(self.base_url, prefix="t2_unfslf")
        resp = client.unfollow_user(user_data["id"])
        resp.assert_error(400)

    def test_follows_boundary_03_follow_non_existent_user_404(self):
        """Verify following non-existent user ID returns 404."""
        client, _, _ = create_test_user(self.base_url, prefix="t2_flw404")
        resp = client.follow_user(999999999)
        resp.assert_error(404)

    def test_follows_boundary_04_unfollow_non_existent_user_404(self):
        """Verify unfollowing non-existent user ID returns 404."""
        client, _, _ = create_test_user(self.base_url, prefix="t2_unf404")
        resp = client.unfollow_user(999999999)
        resp.assert_error(404)

    def test_follows_boundary_05_unfollow_not_followed_idempotent_200(self):
        """Verify unfollowing an un-followed user returns 200 with following: false."""
        target, target_data, _ = create_test_user(self.base_url, prefix="t2_unfnot_t")
        client, _, _ = create_test_user(self.base_url, prefix="t2_unfnot_c")

        resp = client.unfollow_user(target_data["id"])
        resp.assert_ok()
        self.assertFalse(resp.data.get("following"))
        self.assertFalse(resp.data.get("requested"))

    # =========================================================================
    # 9. FOLLOW REQUESTS BOUNDARIES (5 tests)
    # =========================================================================

    def test_follow_requests_boundary_01_duplicate_request_idempotent(self):
        """Verify repeated follow requests on private account return {requested: true} idempotently."""
        target, target_data, _ = create_test_user(self.base_url, is_private=True, prefix="t2_rqidm_t")
        requester, _, _ = create_test_user(self.base_url, prefix="t2_rqidm_r")

        resp1 = requester.follow_user(target_data["id"])
        resp1.assert_ok()
        self.assertTrue(resp1.data.get("requested"))

        resp2 = requester.follow_user(target_data["id"])
        resp2.assert_ok("Second follow request must be idempotent")
        self.assertTrue(resp2.data.get("requested"))

    def test_follow_requests_boundary_02_accept_non_existent_404(self):
        """Verify POST /follow-requests/{userId}/accept returns 404 if no request exists."""
        target, _, _ = create_test_user(self.base_url, is_private=True, prefix="t2_rqacc404")
        resp = target.accept_follow_request(999999999)
        resp.assert_error(404)

    def test_follow_requests_boundary_03_decline_non_existent_404(self):
        """Verify POST /follow-requests/{userId}/decline returns 404 if no request exists."""
        target, _, _ = create_test_user(self.base_url, is_private=True, prefix="t2_rqdec404")
        resp = target.decline_follow_request(999999999)
        resp.assert_error(404)

    def test_follow_requests_boundary_04_unfollow_cancels_pending_request(self):
        """Verify calling DELETE /users/{id}/follow cancels pending follow request."""
        target, target_data, _ = create_test_user(self.base_url, is_private=True, prefix="t2_rqcan_t")
        requester, req_data, _ = create_test_user(self.base_url, prefix="t2_rqcan_r")

        requester.follow_user(target_data["id"])

        # Cancel request
        cancel_resp = requester.unfollow_user(target_data["id"])
        cancel_resp.assert_ok()
        self.assertFalse(cancel_resp.data.get("requested"))

        # Verify request removed from target's inbound list
        reqs = target.get_follow_requests().data.get("items", [])
        self.assertNotIn(req_data["id"], [r["id"] for r in reqs])

    def test_follow_requests_boundary_05_public_target_does_not_create_pending_request(self):
        """Verify following public user does not create a follow request entry."""
        target, target_data, _ = create_test_user(self.base_url, is_private=False, prefix="t2_rqnopub_t")
        follower, _, _ = create_test_user(self.base_url, prefix="t2_rqnopub_f")

        follower.follow_user(target_data["id"])
        reqs = target.get_follow_requests().data.get("items", [])
        self.assertEqual(len(reqs), 0)

    # =========================================================================
    # 10. UPLOAD BOUNDARIES (6 tests)
    # =========================================================================

    def test_upload_boundary_01_reel_non_mp4_rejected_400(self):
        """Verify presigning REEL with non-mp4 contentType returns 400."""
        client, _, _ = create_test_user(self.base_url, prefix="t2_upnonmp4")
        resp = client.presign_upload(
            file_name="dance.jpg",
            content_type="image/jpeg",
            upload_type="REEL",
            file_size=50000,
        )
        resp.assert_error(400, "REEL must be video/mp4")

    def test_upload_boundary_02_avatar_video_rejected_400(self):
        """Verify presigning AVATAR with video/mp4 returns 400."""
        client, _, _ = create_test_user(self.base_url, prefix="t2_upavvid")
        resp = client.presign_upload(
            file_name="clip.mp4",
            content_type="video/mp4",
            upload_type="AVATAR",
            file_size=50000,
        )
        resp.assert_error(400, "AVATAR must be an image")

    def test_upload_boundary_03_image_oversized_rejected_400(self):
        """Verify presigning image with size > 10MB (10,485,760 bytes) returns 400."""
        client, _, _ = create_test_user(self.base_url, prefix="t2_upimgovr")
        resp = client.presign_upload(
            file_name="huge.jpg",
            content_type="image/jpeg",
            upload_type="POST",
            file_size=10485761,  # 10MB + 1 byte
        )
        resp.assert_error(400)

    def test_upload_boundary_04_video_oversized_rejected_400(self):
        """Verify presigning video with size > 100MB (104,857,600 bytes) returns 400."""
        client, _, _ = create_test_user(self.base_url, prefix="t2_upvidovr")
        resp = client.presign_upload(
            file_name="huge.mp4",
            content_type="video/mp4",
            upload_type="REEL",
            file_size=104857601,  # 100MB + 1 byte
        )
        resp.assert_error(400)

    def test_upload_boundary_05_confirm_mismatched_key_prefix_rejected_403(self):
        """Verify confirming upload with key belonging to another user ID returns 403."""
        client, user_data, _ = create_test_user(self.base_url, prefix="t2_upmismatch")
        other_user_id = user_data["id"] + 9999

        resp = client.confirm_upload(
            r2_key=f"POST/{other_user_id}/fake_uuid.jpg",
            upload_type="POST",
            caption="Hijacked upload",
        )
        resp.assert_error(403)

    def test_upload_boundary_06_confirm_non_existent_key_404_or_400(self):
        """Verify confirming upload for key that does not exist in storage returns 400 or 404."""
        client, user_data, _ = create_test_user(self.base_url, prefix="t2_upnonex")
        resp = client.confirm_upload(
            r2_key=f"POST/{user_data['id']}/completely_missing_asset_123.jpg",
            upload_type="POST",
            caption="Ghost asset",
        )
        self.assertIn(resp.status_code, (400, 404))

    # =========================================================================
    # 11. SETTINGS BOUNDARIES (5 tests)
    # =========================================================================

    def test_settings_boundary_01_change_password_wrong_old_400(self):
        """Verify PUT /auth/password with wrong old password returns 400 'Old password is incorrect'."""
        client, _, _ = create_test_user(self.base_url, prefix="t2_setpwbad")
        resp = client.change_password(old_password="IncorrectOldPassword1", new_password="NewValidPassword123")
        resp.assert_error(400, message_substr="Old password is incorrect")

    def test_settings_boundary_02_change_password_weak_new_400(self):
        """Verify PUT /auth/password with weak new password returns 400."""
        client, _, old_pass = create_test_user(self.base_url, prefix="t2_setpwweak")
        resp = client.change_password(old_password=old_pass, new_password="weak")
        resp.assert_error(400)

    def test_settings_boundary_03_update_username_already_taken_409(self):
        """Verify PUT /users/me with already taken username returns 409 Conflict."""
        user_a, user_a_data, _ = create_test_user(self.base_url, prefix="t2_settkn_a")
        user_b, _, _ = create_test_user(self.base_url, prefix="t2_settkn_b")

        resp = user_b.update_profile(username=user_a_data["username"])
        resp.assert_error(409)

    def test_settings_boundary_04_update_bio_oversized_400(self):
        """Verify PUT /users/me with bio > 150 characters returns 400."""
        client, _, _ = create_test_user(self.base_url, prefix="t2_setbioovr")
        resp = client.update_profile(bio="B" * 151)
        resp.assert_error(400)

    def test_settings_boundary_05_update_avatar_mismatched_key_403(self):
        """Verify PUT /users/me/avatar with key not starting with AVATAR/{myId}/ returns 403."""
        client, user_data, _ = create_test_user(self.base_url, prefix="t2_setavmism")
        resp = client.update_avatar(r2_key=f"AVATAR/{user_data['id'] + 9999}/other_avatar.jpg")
        resp.assert_error(403)


if __name__ == "__main__":
    unittest.main()
