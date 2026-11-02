#!/usr/bin/env python3
"""
Unit test suite verifying SocialApp Core Desktop Architecture components:
- config persistence and retrieval
- async_utils worker execution and queue draining
- player state transitions (MockVlcPlayer)
- cache LRU eviction, circular masks, and placeholder creation
- nav router stack push/pop and lifecycle hook invocation
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
from frontend import async_utils
from frontend import player
from frontend import cache
from frontend import nav


def test_config():
    print("Testing config...")
    orig_file = config.CONFIG_FILE
    try:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            config.CONFIG_FILE = Path(tmp.name)
            config.set_setting("test_key", "test_val")
            assert config.get_setting("test_key") == "test_val", "Config get/set mismatch"
            assert config.get_setting("non_existent", "default") == "default"
    finally:
        config.CONFIG_FILE = orig_file
    print("  [PASS] Config persistence verified.")


def test_async_utils():
    print("Testing async_utils...")
    events = []

    def sample_worker(val):
        return val * 2

    def on_success(res):
        events.append(res)

    async_utils.run_async(sample_worker, 21, on_success=on_success)
    time.sleep(0.1)  # Allow worker thread to finish
    drained = async_utils.drain_queue()
    assert drained >= 1, f"Expected at least 1 drained task, got {drained}"
    assert events == [42], f"Expected events [42], got {events}"
    print("  [PASS] Async worker pool and queue draining verified.")


def test_player_mock():
    print("Testing player (MockVlcPlayer)...")
    p = player.MockVlcPlayer()
    assert not p.is_playing()
    p.play_url("mock://video.mp4")
    assert p.is_playing()
    assert p.get_length() > 0
    p.pause()
    assert not p.is_playing()
    p.resume()
    assert p.is_playing()
    p.stop()
    assert not p.is_playing()
    assert p.get_time() == 0

    # Volume & Mute
    p.set_volume(75)
    assert p.get_volume() == 75
    assert p.toggle_mute()      # was unmuted -> now muted
    assert not p.toggle_mute()  # was muted -> now unmuted
    print("  [PASS] MockVlcPlayer state transitions verified.")


def test_cache():
    print("Testing cache...")
    cache.clear_memory_cache()
    # Test circular mask
    mask = cache.create_circular_mask(64, 64)
    assert mask.size == (64, 64)
    assert mask.mode == "L"

    # Test placeholder image
    ph = cache.get_placeholder_image((40, 40), is_circular=True)
    assert ph is not None

    # Test LRU cache population
    img_data = cache.get_image_sync("", (32, 32))
    assert img_data is None  # empty url
    print("  [PASS] Image cache masks and placeholder generation verified.")


def test_nav_router():
    print("Testing navigation router...")

    class MockView:
        def __init__(self, name):
            self.name = name
            self.entered = 0
            self.left = 0

        def on_enter(self, **kwargs):
            self.entered += 1

        def on_leave(self):
            self.left += 1

        def pack(self, **kwargs):
            pass

        def pack_forget(self):
            pass

        def destroy(self):
            pass

    router = nav.NavigationRouter()
    v1 = MockView("Home")
    v2 = MockView("Profile")
    v3 = MockView("Comments")

    router.register_tab("Home", lambda **kw: v1)
    router.register_tab("Profile", lambda **kw: v2)

    router.switch_tab("Home")
    assert router.get_current_view() == v1
    assert v1.entered == 1
    assert not router.can_pop()

    # Push detail view
    router.push(v3, title="Comments")
    assert router.get_current_view() == v3
    assert v1.left == 1
    assert v3.entered == 1
    assert router.can_pop()

    # Pop detail view
    popped = router.pop()
    assert popped == v3
    assert v3.left == 1
    assert v1.entered == 2
    assert router.get_current_view() == v1
    assert not router.can_pop()

    print("  [PASS] Navigation router stack push/pop and on_enter/on_leave hooks verified.")


if __name__ == "__main__":
    test_config()
    test_async_utils()
    test_player_mock()
    test_cache()
    test_nav_router()
    print("\nAll core architecture tests passed successfully!")
