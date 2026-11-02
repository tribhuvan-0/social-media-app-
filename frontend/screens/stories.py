"""
Stories Viewer for SocialApp.
In-window Stories Viewer overlay (360x640) with segmented progress bars, 5-second animated
image countdown, integrated video playback via SharedVlcPlayer, tap-to-navigate,
view telemetry/seen status recording, and auto-advancing through user story groups.

API Calls:
- GET /api/stories -> {items: StoryGroup[]}
- POST /api/stories/{id}/seen -> 204
- DELETE /api/media/{id} -> 204 (for own stories)
"""

import logging
import time
from typing import Any, Callable, Dict, List, Optional

from ..async_utils import run_async
from ..cache import load_image_async
from ..theme import (
    get_theme_colors,
    font_body,
    font_caption,
    font_h2,
    RADIUS_CARD,
    RADIUS_BUTTON,
)
from ..widgets import AvatarView, ConfirmDialog, Toast, format_relative_time

from ..theme import UI_FONT
from ..anim import fade_in_window, pop_button

logger = logging.getLogger("SocialApp.screens.stories")

_HAS_CTK = False
try:
    import customtkinter as ctk
    _HAS_CTK = True
except Exception:
    ctk = None
    _HAS_CTK = False

_ToplevelBase = ctk.CTkToplevel if _HAS_CTK else object
_FrameBase = ctk.CTkFrame if _HAS_CTK else object


class StoriesViewerModal(_ToplevelBase):
    """
    Full Instagram-style Stories Viewer modal overlay (360x640) with segmented timers,
    gesture navigation, and video sync.
    """

    STORY_IMAGE_DURATION_MS = 5000
    TIMER_TICK_MS = 50

    def __init__(
        self,
        parent: Any,
        story_groups: List[Dict[str, Any]],
        initial_group_idx: int = 0,
        api: Any = None,
        player: Any = None,
        on_close: Optional[Callable[[], None]] = None,
        mode: str = "dark",
        **kwargs: Any
    ) -> None:
        self.story_groups = story_groups or []
        self.group_idx = max(0, min(initial_group_idx, len(self.story_groups) - 1)) if self.story_groups else 0
        self.story_idx = 0
        self.api = api
        self.player = player
        self.on_close_callback = on_close
        self.mode = mode

        self.is_paused = False
        self.progress_elapsed_ms = 0
        self._timer_id: Optional[Any] = None
        self._press_time: float = 0.0
        self._segment_bars: List[Any] = []

        if _HAS_CTK and parent is not None:
            super().__init__(parent)
            self.title("Stories")
            self.geometry("360x640")
            self.resizable(False, False)
            self.transient(parent)
            self.configure(fg_color="#000000")
            self.after(100, self._safe_grab)
            fade_in_window(self)

            try:
                x = parent.winfo_x() + (parent.winfo_width() - 360) // 2
                y = parent.winfo_y() + (parent.winfo_height() - 640) // 2
                self.geometry(f"+{max(0, x)}+{max(0, y)}")
            except Exception:
                pass

            self._build_ui()
            self._bind_events()
            self._show_current_story()
        else:
            self._parent = parent

    def _safe_grab(self) -> None:
        try:
            if self.winfo_exists():
                self.grab_set()
        except Exception:
            pass

    def _build_ui(self) -> None:
        if not _HAS_CTK:
            return

        # Main viewport 360x640
        self._viewport = ctk.CTkFrame(self, width=360, height=640, fg_color="#000000", corner_radius=0)
        self._viewport.pack(fill="both", expand=True)
        self._viewport.pack_propagate(False)

        # Media Canvas
        self._media_canvas = ctk.CTkLabel(self._viewport, text="", fg_color="#000000")
        self._media_canvas.place(relx=0, rely=0, relwidth=1.0, relheight=1.0)

        # Top Bar Container
        self._top_bar = ctk.CTkFrame(self._viewport, height=70, fg_color="#121212", corner_radius=0)
        self._top_bar.place(relx=0, rely=0, relwidth=1.0)
        self._top_bar.pack_propagate(False)

        # Segmented Progress Container
        self._segments_container = ctk.CTkFrame(self._top_bar, height=4, fg_color="transparent")
        self._segments_container.pack(fill="x", padx=10, pady=(8, 6))

        # Header: Avatar, Username, Time, Trash, Close
        header_row = ctk.CTkFrame(self._top_bar, fg_color="transparent", height=40)
        header_row.pack(fill="x", padx=10)

        self._avatar = AvatarView(header_row, size=32)
        self._avatar.pack(side="left", padx=(0, 8))

        self._username_lbl = ctk.CTkLabel(
            header_row,
            text="",
            font=font_body(bold=True),
            text_color="#FFFFFF"
        )
        self._username_lbl.pack(side="left", padx=(0, 6))

        self._time_lbl = ctk.CTkLabel(
            header_row,
            text="",
            font=font_caption(),
            text_color="#A8A8A8"
        )
        self._time_lbl.pack(side="left")

        # Close Button
        self._close_btn = ctk.CTkButton(
            header_row,
            text="✕",
            width=28,
            height=28,
            font=(UI_FONT, 16),
            fg_color="transparent",
            text_color="#FFFFFF",
            hover_color="#333333",
            command=self._close
        )
        self._close_btn.pack(side="right")

        # Delete Button (for own stories)
        self._delete_btn = ctk.CTkButton(
            header_row,
            text="🗑",
            width=28,
            height=28,
            font=(UI_FONT, 13),
            fg_color="transparent",
            text_color="#FF3040",
            hover_color="#333333",
            command=self._confirm_delete_current
        )

        # Pause Indicator Overlay
        self._pause_indicator = ctk.CTkLabel(
            self._viewport,
            text="❚❚",
            font=(UI_FONT, 32, "bold"),
            text_color="#CCCCCC"
        )

    def _bind_events(self) -> None:
        if not _HAS_CTK:
            return

        self.bind("<Escape>", lambda e: self._close())
        self.bind("<Left>", lambda e: self._prev_story())
        self.bind("<Right>", lambda e: self._next_story())

        # Tap / Hold gesture handling on canvas
        self._media_canvas.bind("<ButtonPress-1>", self._on_press)
        self._media_canvas.bind("<ButtonRelease-1>", self._on_release)
        self._viewport.bind("<ButtonPress-1>", self._on_press)
        self._viewport.bind("<ButtonRelease-1>", self._on_release)

    def _on_press(self, event: Any) -> None:
        self._press_time = time.time()
        self._pause()

    def _on_release(self, event: Any) -> None:
        duration = time.time() - self._press_time
        self._resume()

        # If short tap (< 250ms), handle left/right split navigation
        if duration < 0.25:
            # Check x coordinate
            x = getattr(event, "x", 180)
            if x < 130:
                self._prev_story()
            else:
                self._next_story()

    def _pause(self) -> None:
        self.is_paused = True
        if self._timer_id and _HAS_CTK and hasattr(self, "tk"):
            self.after_cancel(self._timer_id)
            self._timer_id = None
        if self.player:
            try:
                self.player.pause()
            except Exception:
                pass
        if _HAS_CTK and hasattr(self, "_pause_indicator"):
            self._pause_indicator.place(relx=0.5, rely=0.5, anchor="center")

    def _resume(self) -> None:
        self.is_paused = False
        if _HAS_CTK and hasattr(self, "_pause_indicator"):
            self._pause_indicator.place_forget()
        if self.player:
            try:
                self.player.resume()
            except Exception:
                pass
        self._start_timer()

    def _get_current_story(self) -> Optional[Dict[str, Any]]:
        if not self.story_groups or self.group_idx >= len(self.story_groups):
            return None
        stories = self.story_groups[self.group_idx].get("stories", [])
        if not stories or self.story_idx >= len(stories):
            return None
        return stories[self.story_idx]

    def _show_current_story(self) -> None:
        if not self.story_groups or self.group_idx >= len(self.story_groups):
            self._close()
            return

        group = self.story_groups[self.group_idx]
        user = group.get("user", {})
        stories = group.get("stories", [])

        if not stories or self.story_idx >= len(stories):
            # Advance to next group
            self._next_group()
            return

        story = stories[self.story_idx]
        story_id = story.get("id", 0)
        media_url = story.get("mediaUrl", "")
        media_kind = story.get("mediaKind", "IMAGE")
        created_at = story.get("createdAt", "")

        # Stop previous playback
        if self.player:
            try:
                self.player.stop()
            except Exception:
                pass

        if not _HAS_CTK or not hasattr(self, "_username_lbl"):
            # Still mark seen in headless mode
            if self.api and story_id:
                run_async(self.api.mark_story_seen, story_id)
            story["seen"] = True
            return

        # Update header
        self._username_lbl.configure(text=user.get("username", "user"))
        self._time_lbl.configure(text=format_relative_time(created_at))
        self._avatar.set_image(user.get("avatarUrl", ""))

        # Check delete permission (own story)
        me_id = getattr(self.api, "_current_user_id", None)
        if user.get("id") == me_id:
            self._delete_btn.pack(side="right", padx=(0, 6))
        else:
            self._delete_btn.pack_forget()

        # Rebuild segmented bars
        self._rebuild_segment_bars(len(stories), self.story_idx)

        # Reset progress
        self.progress_elapsed_ms = 0

        # Load Media
        if media_kind == "VIDEO":
            self._media_canvas.place_forget()
            if self.player:
                self._viewport.update_idletasks()
                self.player.play_url(media_url, widget=self._viewport, loop=False)
        else:
            self._media_canvas.place(relx=0, rely=0, relwidth=1.0, relheight=1.0)
            self._top_bar.lift()
            # Display image
            def on_img_ready(wrapped: Any) -> None:
                try:
                    self._media_canvas.configure(image=wrapped)
                except Exception:
                    pass

            placeholder = load_image_async(media_url, (360, 640), on_ready=on_img_ready)
            self._media_canvas.configure(image=placeholder)

        # Record story seen
        story["seen"] = True
        if self.api and story_id:
            run_async(lambda sid=story_id: self.api.mark_story_seen(sid))

        # Start timer countdown
        self._start_timer()

    def _rebuild_segment_bars(self, total: int, active_idx: int) -> None:
        if not _HAS_CTK or not hasattr(self, "_segments_container"):
            return

        for child in self._segments_container.winfo_children():
            child.destroy()
        self._segment_bars.clear()

        if total <= 0:
            return

        for i in range(total):
            seg_bg = ctk.CTkFrame(
                self._segments_container,
                height=3,
                fg_color="#555555",
                corner_radius=2
            )
            seg_bg.pack(side="left", fill="x", expand=True, padx=2)

            # Filled inner bar
            fill_color = "#FFFFFF" if i <= active_idx else "transparent"
            fill_width = 1.0 if i < active_idx else (0.0 if i > active_idx else 0.0)

            seg_fill = ctk.CTkFrame(
                seg_bg,
                height=3,
                fg_color="#FFFFFF" if i < active_idx else "#FFFFFF",
                corner_radius=2
            )
            if fill_width > 0:
                seg_fill.place(relx=0, rely=0, relwidth=fill_width, relheight=1.0)

            self._segment_bars.append((seg_bg, seg_fill))

    def _start_timer(self) -> None:
        if self._timer_id and _HAS_CTK and hasattr(self, "tk"):
            self.after_cancel(self._timer_id)
            self._timer_id = None

        if self.is_paused or not _HAS_CTK or not hasattr(self, "tk"):
            return

        self._tick()

    def _tick(self) -> None:
        if self.is_paused or not _HAS_CTK or not hasattr(self, "tk"):
            return

        self.progress_elapsed_ms += self.TIMER_TICK_MS
        story = self._get_current_story()
        is_video = story and story.get("mediaKind") == "VIDEO"

        if is_video and self.player:
            dur = self.player.get_length() or self.STORY_IMAGE_DURATION_MS
            cur_time = self.player.get_time()
            progress = min(1.0, max(0.0, cur_time / max(1, dur)))
            is_finished = not self.player.is_playing() and cur_time >= dur - 200
        else:
            progress = min(1.0, self.progress_elapsed_ms / self.STORY_IMAGE_DURATION_MS)
            is_finished = (self.progress_elapsed_ms >= self.STORY_IMAGE_DURATION_MS)

        # Update active segment width
        if self.story_idx < len(self._segment_bars):
            _, fill_widget = self._segment_bars[self.story_idx]
            fill_widget.place(relx=0, rely=0, relwidth=progress, relheight=1.0)

        if is_finished:
            self._next_story()
        else:
            self._timer_id = self.after(self.TIMER_TICK_MS, self._tick)

    def _next_story(self) -> None:
        if not self.story_groups:
            self._close()
            return

        stories = self.story_groups[self.group_idx].get("stories", [])
        if self.story_idx + 1 < len(stories):
            self.story_idx += 1
            self._show_current_story()
        else:
            self._next_group()

    def _prev_story(self) -> None:
        if self.story_idx > 0:
            self.story_idx -= 1
            self._show_current_story()
        elif self.group_idx > 0:
            self.group_idx -= 1
            prev_stories = self.story_groups[self.group_idx].get("stories", [])
            self.story_idx = max(0, len(prev_stories) - 1)
            self._show_current_story()
        else:
            # Replay first story
            self.story_idx = 0
            self._show_current_story()

    def _next_group(self) -> None:
        if self.group_idx + 1 < len(self.story_groups):
            self.group_idx += 1
            self.story_idx = 0
            self._show_current_story()
        else:
            # Reached end of all stories
            self._close()

    def _confirm_delete_current(self) -> None:
        story = self._get_current_story()
        if not story:
            return
        story_id = story.get("id", 0)

        self._pause()
        ConfirmDialog(
            self,
            title="Delete Story",
            message="Delete this story? This cannot be undone.",
            confirm_text="Delete",
            on_confirm=lambda: self._delete_current_story(story_id)
        )

    def _delete_current_story(self, story_id: int) -> None:
        def worker() -> None:
            if self.api:
                self.api.delete_media(story_id)

        def on_success(_: Any) -> None:
            # Remove from local list
            group = self.story_groups[self.group_idx]
            group["stories"] = [s for s in group.get("stories", []) if s.get("id") != story_id]
            if not group["stories"]:
                # Remove empty group
                self.story_groups.pop(self.group_idx)
                self.story_idx = 0
            self._show_current_story()

        def on_error(exc: Exception) -> None:
            logger.warning("Failed to delete story: %s", exc)
            self._resume()

        run_async(worker, on_success=on_success, on_error=on_error)

    def _close(self) -> None:
        if self._timer_id and _HAS_CTK and hasattr(self, "tk"):
            try:
                self.after_cancel(self._timer_id)
            except Exception:
                pass
            self._timer_id = None

        if self.player:
            try:
                self.player.stop()
            except Exception:
                pass

        if _HAS_CTK and hasattr(self, "tk"):
            try:
                self.grab_release()
                self.destroy()
            except Exception:
                pass

        if self.on_close_callback:
            self.on_close_callback()


class StoriesScreen(_FrameBase):
    """
    Stand-alone view or wrapper for StoriesViewer integration in navigation router.
    """

    def __init__(self, master: Any, app_state: Any = None, mode: str = "dark", **kwargs: Any) -> None:
        self.app_state = app_state
        self.mode = mode
        if _HAS_CTK:
            super().__init__(master, fg_color="#000000", **kwargs)
            lbl = ctk.CTkLabel(
                self,
                text="Tap on any user story to view.",
                font=font_body(),
                text_color="#A8A8A8"
            )
            lbl.place(relx=0.5, rely=0.5, anchor="center")

    def open_viewer(
        self,
        story_groups: List[Dict[str, Any]],
        initial_idx: int = 0,
        on_close: Optional[Callable[[], None]] = None
    ) -> Optional[StoriesViewerModal]:
        if not _HAS_CTK:
            return None
        api = self.app_state.api if self.app_state else None
        player = self.app_state.player if self.app_state else None
        parent = self.winfo_toplevel()
        return StoriesViewerModal(
            parent=parent,
            story_groups=story_groups,
            initial_group_idx=initial_idx,
            api=api,
            player=player,
            on_close=on_close,
            mode=self.mode
        )

    def on_enter(self, **kwargs: Any) -> None:
        pass

    def on_leave(self) -> None:
        pass
