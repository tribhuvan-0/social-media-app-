#!/usr/bin/env python3
"""
Comprehensive automated test suite for MockApi contract compliance.
Imports MockApi and exercises every single method, validating schema adherence
against the official SocialApp API specification in docs.md.
"""

import os
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from frontend.mock_api import MockApi
from frontend.api import ApiError


class TestContractValidator:
    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.api = MockApi()

    def assert_true(self, condition: bool, message: str) -> None:
        if condition:
            self.passed += 1
            print(f"  [PASS] {message}")
        else:
            self.failed += 1
            print(f"  [FAIL] {message}")
            raise AssertionError(message)

    def validate_user_summary(self, user: dict, context: str) -> None:
        expected_keys = {"id", "username", "avatarUrl", "followedByMe", "requestedByMe"}
        self.assert_true(
            expected_keys.issubset(user.keys()),
            f"{context}: UserSummary has required fields ({expected_keys})"
        )
        self.assert_true(isinstance(user["id"], int), f"{context}: user.id is int")
        self.assert_true(isinstance(user["username"], str), f"{context}: user.username is str")
        self.assert_true(isinstance(user["avatarUrl"], str), f"{context}: user.avatarUrl is str")
        self.assert_true(isinstance(user["followedByMe"], bool), f"{context}: user.followedByMe is bool")
        self.assert_true(isinstance(user["requestedByMe"], bool), f"{context}: user.requestedByMe is bool")

    def validate_me(self, me: dict, context: str) -> None:
        expected_keys = {"id", "username", "email", "bio", "avatarUrl", "isPrivate", "notificationsEnabled"}
        self.assert_true(
            expected_keys.issubset(me.keys()),
            f"{context}: Me has required fields ({expected_keys})"
        )
        self.assert_true(isinstance(me["id"], int), f"{context}: me.id is int")
        self.assert_true(isinstance(me["username"], str), f"{context}: me.username is str")
        self.assert_true(isinstance(me["email"], str), f"{context}: me.email is str")
        self.assert_true(isinstance(me["isPrivate"], bool), f"{context}: me.isPrivate is bool")
        self.assert_true(isinstance(me["notificationsEnabled"], bool), f"{context}: me.notificationsEnabled is bool")

    def validate_media_card(self, card: dict, context: str) -> None:
        expected_keys = {
            "id", "type", "mediaKind", "mediaUrl", "thumbnailUrl", "caption",
            "tags", "createdAt", "likeCount", "commentCount", "shareCount",
            "likedByMe", "user"
        }
        self.assert_true(
            expected_keys.issubset(card.keys()),
            f"{context}: MediaCard has required fields ({expected_keys})"
        )
        self.assert_true(card["type"] in ("POST", "REEL", "STORY"), f"{context}: card.type valid")
        self.assert_true(card["mediaKind"] in ("IMAGE", "VIDEO"), f"{context}: card.mediaKind valid")
        self.assert_true(isinstance(card["tags"], list), f"{context}: card.tags is list")
        self.assert_true(isinstance(card["likeCount"], int), f"{context}: card.likeCount is int")
        self.assert_true(isinstance(card["likedByMe"], bool), f"{context}: card.likedByMe is bool")
        self.validate_user_summary(card["user"], f"{context} -> user")

    def validate_comment(self, comment: dict, context: str) -> None:
        expected_keys = {"id", "mediaId", "text", "createdAt", "user"}
        self.assert_true(
            expected_keys.issubset(comment.keys()),
            f"{context}: Comment has required fields ({expected_keys})"
        )
        self.assert_true(isinstance(comment["id"], int), f"{context}: comment.id is int")
        self.assert_true(isinstance(comment["mediaId"], int), f"{context}: comment.mediaId is int")
        self.assert_true(isinstance(comment["text"], str), f"{context}: comment.text is str")
        self.validate_user_summary(comment["user"], f"{context} -> user")

    def validate_profile(self, profile: dict, context: str) -> None:
        expected_keys = {
            "id", "username", "bio", "avatarUrl", "isPrivate", "isMe",
            "postCount", "followerCount", "followingCount", "followedByMe",
            "requestedByMe", "canView"
        }
        self.assert_true(
            expected_keys.issubset(profile.keys()),
            f"{context}: Profile has required fields ({expected_keys})"
        )
        self.assert_true(isinstance(profile["isMe"], bool), f"{context}: profile.isMe is bool")
        self.assert_true(isinstance(profile["canView"], bool), f"{context}: profile.canView is bool")
        self.assert_true(isinstance(profile["followerCount"], int), f"{context}: profile.followerCount is int")

    def validate_grid_item(self, item: dict, context: str) -> None:
        expected_keys = {"id", "type", "mediaKind", "thumbnailUrl"}
        self.assert_true(
            expected_keys.issubset(item.keys()),
            f"{context}: GridItem has required fields ({expected_keys})"
        )

    def run_all_tests(self) -> None:
        print("==================================================")
        print("  Running MockApi Contract & Behavior Tests")
        print("==================================================")

        # 1. Auth Flow
        print("\n[Group 1: Authentication]")
        me = self.api.get_me()
        self.validate_me(me, "get_me")

        signup_res = self.api.signup("test_newuser", "newuser@example.com", "Password123")
        self.assert_true("token" in signup_res, "signup returns token")
        self.validate_me(signup_res["user"], "signup user")

        login_res = self.api.login("alex_adventures", "Password123")
        self.assert_true("token" in login_res, "login returns token")
        self.validate_me(login_res["user"], "login user")

        self.api.change_password("Password123", "NewSecretPass456")
        self.assert_true(True, "change_password succeeded without error")

        # 2. Feed & Suggestions
        print("\n[Group 2: Feed & Suggestions]")
        feed = self.api.get_feed(page=0, size=5)
        self.assert_true("items" in feed and "hasNext" in feed, "feed response shape")
        self.assert_true(len(feed["items"]) > 0, "feed returned items")
        self.validate_media_card(feed["items"][0], "feed[0]")

        suggested = self.api.get_suggested_users()
        self.assert_true("items" in suggested, "suggested response shape")
        self.assert_true(len(suggested["items"]) > 0, "suggested returned users")
        self.validate_user_summary(suggested["items"][0], "suggested[0]")

        # 3. Stories Flow
        print("\n[Group 3: Stories]")
        stories = self.api.get_stories()
        self.assert_true("items" in stories, "stories response shape")
        self.assert_true(len(stories["items"]) > 0, "stories returned groups")
        group = stories["items"][0]
        self.assert_true("user" in group and "stories" in group, "story group structure")
        self.validate_user_summary(group["user"], "story group user")
        story_item = group["stories"][0]
        self.assert_true("mediaUrl" in story_item and "expiresAt" in story_item, "story item structure")
        self.api.mark_story_seen(story_item["id"])
        self.assert_true(True, "mark_story_seen executed")

        # 4. Reels Flow
        print("\n[Group 4: Reels]")
        reels = self.api.get_reels(size=3)
        self.assert_true("items" in reels and "hasNext" in reels, "reels response shape")
        self.assert_true(len(reels["items"]) > 0, "reels returned items")
        reel_card = reels["items"][0]
        self.validate_media_card(reel_card, "reel[0]")
        self.assert_true(reel_card["type"] == "REEL", "reel card type is REEL")

        # 5. Media Interactions (Get, Like, Unlike, Share, View Telemetry)
        print("\n[Group 5: Media Interactions]")
        test_media_id = reel_card["id"]
        detail = self.api.get_media(test_media_id)
        self.validate_media_card(detail, f"get_media({test_media_id})")

        like_res = self.api.like_media(test_media_id)
        self.assert_true(like_res["liked"] is True, "like_media sets liked=True")
        self.assert_true(like_res["likeCount"] > 0, "like_media increments count")

        unlike_res = self.api.unlike_media(test_media_id)
        self.assert_true(unlike_res["liked"] is False, "unlike_media sets liked=False")

        share_res = self.api.share_media(test_media_id)
        self.assert_true("shareUrl" in share_res and "shareCount" in share_res, "share_media response")

        self.api.send_view_telemetry(test_media_id, watch_ms=12500, duration_ms=15000, completed=True)
        self.assert_true(True, "send_view_telemetry executed")

        # 6. Comments Flow
        print("\n[Group 6: Comments]")
        comments = self.api.get_comments(test_media_id, page=0, size=10)
        self.assert_true("items" in comments and "hasNext" in comments, "comments response shape")
        new_comment = self.api.add_comment(test_media_id, "Automated test comment 🎯")
        self.validate_comment(new_comment, "add_comment")
        self.assert_true(new_comment["text"] == "Automated test comment 🎯", "comment text matched")

        self.api.delete_comment(new_comment["id"])
        self.assert_true(True, "delete_comment executed")

        # 7. Users, Follows, and Profiles
        print("\n[Group 7: Users & Profiles]")
        target_uid = 2  # Sarah Codes
        profile = self.api.get_profile(target_uid)
        self.validate_profile(profile, f"get_profile({target_uid})")

        user_posts = self.api.get_user_posts(target_uid, page=0, size=6)
        self.assert_true("items" in user_posts, "get_user_posts response shape")
        if user_posts["items"]:
            self.validate_grid_item(user_posts["items"][0], "user_posts[0]")

        followers = self.api.get_followers(target_uid, page=0, size=5)
        self.assert_true("items" in followers, "get_followers response shape")

        following = self.api.get_following(target_uid, page=0, size=5)
        self.assert_true("items" in following, "get_following response shape")

        follow_res = self.api.follow_user(4)  # Follow Elena
        self.assert_true("following" in follow_res, "follow_user response shape")
        unfollow_res = self.api.unfollow_user(4)
        self.assert_true(unfollow_res["following"] is False, "unfollow_user response shape")

        updated_profile = self.api.update_profile(bio="Updated test bio for automation!")
        self.assert_true(updated_profile["bio"] == "Updated test bio for automation!", "update_profile bio")

        settings_res = self.api.update_settings(is_private=False, notifications_enabled=True)
        self.assert_true(settings_res["isPrivate"] is False, "update_settings isPrivate")

        # Follow requests
        f_requests = self.api.get_follow_requests()
        self.assert_true("items" in f_requests, "get_follow_requests response shape")

        # 8. Upload Flow
        print("\n[Group 8: Upload Flow]")
        presign = self.api.presign_upload(
            file_name="sunset_mountain.jpg",
            content_type="image/jpeg",
            media_type="POST",
            file_size=204800
        )
        self.assert_true("uploadUrl" in presign and "r2Key" in presign, "presign_upload response shape")

        # Binary upload
        prog_events = []
        self.api.upload_file_binary(
            presign["uploadUrl"],
            b"fake_image_bytes_content_for_test",
            "image/jpeg",
            progress_callback=lambda s, t: prog_events.append((s, t))
        )
        self.assert_true(len(prog_events) > 0, "upload_file_binary invoked progress_callback")

        # Confirm upload
        confirmed = self.api.confirm_upload(
            presign["r2Key"],
            "POST",
            caption="Verified upload test post! #awesome #sunset"
        )
        self.validate_media_card(confirmed, "confirm_upload")
        self.assert_true("awesome" in confirmed["tags"], "caption hashtag extraction confirmed")

        # Delete uploaded media
        self.api.delete_media(confirmed["id"])
        self.assert_true(True, "delete_media on uploaded item succeeded")

        print("\n==================================================")
        print(f"  Test Results: {self.passed} Passed, {self.failed} Failed")
        print("==================================================")
        if self.failed > 0:
            sys.exit(1)


if __name__ == "__main__":
    validator = TestContractValidator()
    validator.run_all_tests()
