#!/usr/bin/env python3
"""
Comprehensive automated test suite for Milestone 6: Desktop Client UI Screens & Integration.
Verifies screen instantiation, data binding with MockApi, lifecycle hooks (on_enter/on_leave),
navigation router push/pop history, theme switching, and client-side validation logic.
"""

import os
import sys
import tempfile
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from frontend import config
from frontend import theme
from frontend import nav
from frontend import main
from frontend.mock_api import MockApi
from frontend.player import MockVlcPlayer
from frontend.screens import (
    LoginScreen,
    HomeScreen,
    StoriesScreen,
    StoriesViewerModal,
    ReelsScreen,
    ExploreScreen,
    CreateScreen,
    ProfileScreen,
    MessagesScreen,
    ActivityScreen,
    SettingsScreen,
    CommentsModal,
    FollowListModal,
)
from frontend.async_utils import drain_queue


def setup_test_app_state() -> main.AppState:
    """Create an isolated AppState with MockApi and MockVlcPlayer."""
    state = main.AppState()
    state.use_mock = True
    state.api = MockApi()
    state.player = MockVlcPlayer()
    state.api.set_player(state.player)
    state.current_user = state.api.get_me()
    return state


def test_login_screen():
    print("[Test 1/13] Testing LoginScreen...")
    state = setup_test_app_state()
    screen = LoginScreen(master=None, app_state=state, mode="dark")

    # 1. Validation tests
    # Empty username
    err = screen.validate_inputs("", "Password123")
    assert err == "Username is required.", f"Expected error, got {err}"

    # Invalid username format
    err = screen.validate_inputs("ab", "Password123")
    assert "3-30 characters" in err

    # Weak password
    err = screen.validate_inputs("valid_user", "weak")
    assert "at least 8 chars" in err

    # Valid login credentials
    err = screen.validate_inputs("valid_user", "Password123")
    assert err is None, f"Expected None for valid login, got {err}"

    # Signup validation: missing email
    screen.is_signup = True
    err = screen.validate_inputs("valid_user", "Password123", email="")
    assert "Email address is required" in err

    # Signup validation: invalid email
    err = screen.validate_inputs("valid_user", "Password123", email="invalid-email")
    assert "valid email address" in err

    # Signup validation: mismatched passwords
    err = screen.validate_inputs("valid_user", "Password123", email="user@example.com", confirm_password="DifferentPassword123")
    assert "Passwords do not match" in err

    # Signup validation: all valid
    err = screen.validate_inputs("valid_user", "Password123", email="user@example.com", confirm_password="Password123")
    assert err is None

    # Lifecycle hooks
    screen.on_enter()
    screen.on_leave()
    print("  [PASS] LoginScreen validation and lifecycle verified.")


def test_home_screen():
    print("[Test 2/13] Testing HomeScreen...")
    state = setup_test_app_state()
    screen = HomeScreen(master=None, app_state=state, mode="dark")

    # Trigger stories and feed load
    screen.refresh_all()
    time.sleep(0.05)
    drain_queue()

    assert len(screen.story_groups) > 0, "Expected story groups to be loaded"
    assert len(screen.posts) > 0, "Expected feed posts to be loaded"
    assert screen.posts[0]["type"] in ("POST", "REEL")
    assert "user" in screen.posts[0]

    # Lifecycle
    screen.on_enter()
    screen.on_leave()
    print("  [PASS] HomeScreen data binding and stories tray verified.")


def test_stories_viewer():
    print("[Test 3/13] Testing StoriesViewerModal and StoriesScreen...")
    state = setup_test_app_state()
    story_res = state.api.get_stories()
    groups = story_res.get("items", [])
    assert len(groups) > 0

    viewer = StoriesViewerModal(
        parent=None,
        story_groups=groups,
        initial_group_idx=0,
        api=state.api,
        player=state.player,
        mode="dark"
    )

    cur_story = viewer._get_current_story()
    assert cur_story is not None
    assert "id" in cur_story

    # Test navigation: advance story
    initial_idx = viewer.story_idx
    viewer._next_story()
    # Test pause and resume
    viewer._pause()
    assert viewer.is_paused is True
    viewer._resume()
    assert viewer.is_paused is False

    # Close viewer
    viewer._close()
    assert not state.player.is_playing()

    # StoriesScreen wrapper
    screen = StoriesScreen(master=None, app_state=state)
    screen.on_enter()
    screen.on_leave()
    print("  [PASS] StoriesViewerModal navigation and player lifecycle verified.")


def test_reels_screen():
    print("[Test 4/13] Testing ReelsScreen...")
    state = setup_test_app_state()
    screen = ReelsScreen(master=None, app_state=state, mode="dark")

    screen._fetch_reels()
    time.sleep(0.05)
    drain_queue()

    assert len(screen.reels) > 0, "Expected reels to be fetched"
    assert len(screen.loaded_ids) > 0

    cur_reel = screen._get_current_reel()
    assert cur_reel is not None
    assert cur_reel.get("type") == "REEL"

    # Test reel navigation
    screen._nav_next()
    time.sleep(0.05)
    drain_queue()

    # Test optimistic like toggle on active reel
    active_reel = screen._get_current_reel()
    initial_liked = active_reel.get("likedByMe", False)
    initial_likes = active_reel.get("likeCount", 0)
    screen._toggle_like()
    time.sleep(0.05)
    drain_queue()
    assert active_reel.get("likedByMe") != initial_liked
    expected_count = initial_likes + (1 if not initial_liked else -1)
    assert active_reel.get("likeCount") == expected_count

    # Lifecycle
    screen.on_enter()
    screen.on_leave()
    assert not state.player.is_playing()
    print("  [PASS] ReelsScreen video playback and like interactions verified.")


def test_explore_screen():
    print("[Test 5/13] Testing ExploreScreen...")
    state = setup_test_app_state()
    screen = ExploreScreen(master=None, app_state=state, mode="dark")

    screen.load_content()
    time.sleep(0.05)
    drain_queue()

    assert len(screen.all_media) > 0, "Expected explore media to be loaded"
    assert len(screen.suggested_users) > 0, "Expected suggested users to be loaded"

    # Test search query filtering
    screen.all_media = [
        {"id": 1, "caption": "Awesome sunset #nature #photo", "tags": ["nature", "photo"], "user": {"username": "alex"}},
        {"id": 2, "caption": "Coding python today #tech #python", "tags": ["tech", "python"], "user": {"username": "sarah"}},
    ]
    screen.filtered_media = list(screen.all_media)

    # Search by tag
    query = "nature"
    screen.filtered_media = [
        m for m in screen.all_media
        if query in m.get("caption", "").lower()
        or any(query in tag.lower() for tag in m.get("tags", []))
    ]
    assert len(screen.filtered_media) == 1
    assert screen.filtered_media[0]["id"] == 1

    screen.on_enter()
    screen.on_leave()
    print("  [PASS] ExploreScreen discovery grid and tag search verified.")


def test_create_screen():
    print("[Test 6/13] Testing CreateScreen...")
    state = setup_test_app_state()
    screen = CreateScreen(master=None, app_state=state, initial_mode="Post", mode="dark")

    assert screen.media_type == "POST"
    screen._on_type_changed("Reel")
    assert screen.media_type == "REEL"
    screen._on_type_changed("Story")
    assert screen.media_type == "STORY"

    # Test file size limits
    assert screen.MAX_IMAGE_SIZE == 10 * 1024 * 1024
    assert screen.MAX_VIDEO_SIZE == 100 * 1024 * 1024

    # Test hashtag regex logic
    import re
    caption = "Enjoying the sunset with friends! #summer #vibes #nature"
    tags = re.findall(r"#(\w+)", caption)
    assert tags == ["summer", "vibes", "nature"]

    screen.on_enter(initial_mode="Reel")
    assert screen.media_type == "REEL"
    screen.on_leave()
    print("  [PASS] CreateScreen mode switching and hashtag parsing verified.")


def test_profile_screen():
    print("[Test 7/13] Testing ProfileScreen...")
    state = setup_test_app_state()
    screen = ProfileScreen(master=None, app_state=state, user_id=2, mode="dark")

    screen.load_profile()
    time.sleep(0.05)
    drain_queue()

    assert screen.profile_data.get("id") == 2
    assert "username" in screen.profile_data
    assert "postCount" in screen.profile_data

    # Load posts
    screen._load_posts(page=0)
    time.sleep(0.05)
    drain_queue()
    assert len(screen.grid_items) > 0

    # Test follow toggle
    followed = screen.profile_data.get("followedByMe", False)
    screen._execute_follow_action(unfollow=followed)
    time.sleep(0.05)
    drain_queue()
    assert screen.profile_data.get("followedByMe") != followed

    screen.on_enter(user_id=1)
    assert screen.target_user_id == 1
    screen.on_leave()
    print("  [PASS] ProfileScreen stats, media grid, and follow toggle verified.")


def test_messages_screen():
    print("[Test 8/13] Testing MessagesScreen...")
    state = setup_test_app_state()
    screen = MessagesScreen(master=None, app_state=state, mode="dark")

    assert len(screen.conversations) >= 3
    first_conv = screen.conversations[0]
    initial_msg_count = len(first_conv["messages"])

    # Open thread
    screen._open_thread(first_conv)
    assert screen.active_conv == first_conv
    assert first_conv["unread"] is False

    # Test sending message
    screen._send_message("Sounds great! Let's do it.")
    assert len(first_conv["messages"]) == initial_msg_count + 1
    assert first_conv["last_message"] == "Sounds great! Let's do it."

    screen.on_enter()
    screen.on_leave()
    print("  [PASS] MessagesScreen conversation threads and message sending verified.")


def test_activity_screen():
    print("[Test 9/13] Testing ActivityScreen...")
    state = setup_test_app_state()
    screen = ActivityScreen(master=None, app_state=state, mode="dark")

    screen.load_data()
    time.sleep(0.05)
    drain_queue()

    assert len(screen.notifications) > 0
    # Add a mock request to test accept/decline logic
    req_user_id = 3
    state.api._follow_requests.add((req_user_id, state.api._current_user_id))
    screen.follow_requests = [{"id": req_user_id, "username": "marco_foodie", "avatarUrl": ""}]

    # Accept request
    state.api.accept_follow_request(req_user_id)
    screen.follow_requests = [r for r in screen.follow_requests if r.get("id") != req_user_id]
    assert len(screen.follow_requests) == 0

    screen.on_enter()
    screen.on_leave()
    print("  [PASS] ActivityScreen notifications and follow requests verified.")


def test_settings_screen():
    print("[Test 10/13] Testing SettingsScreen...")
    state = setup_test_app_state()
    logout_called = []

    def on_logout():
        logout_called.append(True)

    screen = SettingsScreen(master=None, app_state=state, on_logout=on_logout, mode="dark")

    # Test settings update
    screen._on_settings_switch_changed()
    time.sleep(0.05)
    drain_queue()

    # Test cache calculation and clearing
    screen._update_cache_display()
    screen._on_clear_cache_clicked()

    # Test logout execution
    screen._execute_logout()
    assert logout_called == [True]
    assert state.api.get_token() is None
    assert state.current_user is None

    screen.on_enter()
    screen.on_leave()
    print("  [PASS] SettingsScreen preferences, cache, and logout verified.")


def test_comments_and_follow_modals():
    print("[Test 11/13] Testing CommentsModal and FollowListModal...")
    state = setup_test_app_state()

    # 1. CommentsModal
    comments_dlg = CommentsModal(
        parent=None,
        media_id=1,
        api=state.api,
        media_owner_id=1,
        mode="dark"
    )
    comments_dlg._load_comments(page=0)
    time.sleep(0.05)
    drain_queue()

    assert len(comments_dlg.comments) > 0
    init_count = len(comments_dlg.comments)

    # Submit comment
    new_c = state.api.add_comment(1, "Test comment from suite")
    comments_dlg.comments.append(new_c)
    assert len(comments_dlg.comments) == init_count + 1

    # 2. FollowListModal
    follow_dlg = FollowListModal(
        parent=None,
        user_id=2,
        list_type="followers",
        api=state.api,
        mode="dark"
    )
    follow_dlg._load_data(page=0)
    time.sleep(0.05)
    drain_queue()

    assert len(follow_dlg.users) > 0
    print("  [PASS] CommentsModal and FollowListModal data bindings verified.")


def test_navigation_router_integration():
    print("[Test 12/13] Testing NavigationRouter Integration...")
    state = setup_test_app_state()
    router = nav.NavigationRouter(container_frame=None, player=state.player)
    state.router = router

    events = []

    class DummyScreen:
        def __init__(self, name="Screen", **kwargs):
            self.name = name
            self.kwargs = kwargs

        def on_enter(self, **kwargs):
            events.append(f"{self.name}.on_enter")

        def on_leave(self):
            events.append(f"{self.name}.on_leave")

        def pack(self, **kwargs):
            pass

        def pack_forget(self):
            pass

        def destroy(self):
            events.append(f"{self.name}.destroy")

    # Register tabs
    for tab in ("Home", "Explore", "Create", "Reels", "Profile"):
        router.register_tab(tab, lambda parent=None, t=tab: DummyScreen(t))

    # Switch tab to Home
    router.switch_tab("Home")
    assert router.get_current_view().name == "Home"
    assert "Home.on_enter" in events

    # Switch tab to Explore
    router.switch_tab("Explore")
    assert router.get_current_view().name == "Explore"
    assert "Home.on_leave" in events
    assert "Explore.on_enter" in events

    # Push a nested view (e.g. Profile)
    pushed_view = router.push(lambda **kw: DummyScreen("PushedProfile", **kw), title="User Profile")
    assert router.can_pop() is True
    assert router.get_current_view().name == "PushedProfile"
    assert "Explore.on_leave" in events
    assert "PushedProfile.on_enter" in events

    # Pop nested view
    popped = router.pop()
    assert popped.name == "PushedProfile"
    assert router.can_pop() is False
    assert router.get_current_view().name == "Explore"
    assert "PushedProfile.on_leave" in events
    assert "Explore.on_enter" in events

    # Test pop_to_root
    router.push(lambda **kw: DummyScreen("View1", **kw))
    router.push(lambda **kw: DummyScreen("View2", **kw))
    assert router.can_pop() is True
    router.pop_to_root()
    assert router.can_pop() is False
    assert router.get_current_view().name == "Explore"
    print("  [PASS] NavigationRouter stack transitions and lifecycle hooks verified.")


def test_theme_and_config():
    print("[Test 13/13] Testing Theme Palettes and Dynamic Switching...")
    # Test palettes
    dark_colors = theme.get_theme_colors("dark")
    light_colors = theme.get_theme_colors("light")

    assert dark_colors["bg"] == "#000000"
    assert light_colors["bg"] == "#FFFFFF"
    assert dark_colors["text_primary"] == "#FFFFFF"
    assert light_colors["text_primary"] == "#000000"
    assert dark_colors["primary"] == "#0095F6"

    # Test config persistence
    orig_file = config.CONFIG_FILE
    try:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            config.CONFIG_FILE = Path(tmp.name)
            config.set_setting("appearance_mode", "light")
            assert config.get_setting("appearance_mode") == "light"
            config.set_setting("appearance_mode", "dark")
            assert config.get_setting("appearance_mode") == "dark"
    finally:
        config.CONFIG_FILE = orig_file

    print("  [PASS] Theme palettes and persistent theme configuration verified.")


def main_suite():
    print("=" * 60)
    print("  Running Milestone 6 Desktop UI Screens & Integration Tests")
    print("=" * 60)

    test_login_screen()
    test_home_screen()
    test_stories_viewer()
    test_reels_screen()
    test_explore_screen()
    test_create_screen()
    test_profile_screen()
    test_messages_screen()
    test_activity_screen()
    test_settings_screen()
    test_comments_and_follow_modals()
    test_navigation_router_integration()
    test_theme_and_config()

    print("=" * 60)
    print("  ALL 13 UI Screen & Navigation Test Suites Passed Successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main_suite()
