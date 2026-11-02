"""
Reels Recommended Video Screen for SocialApp.
Full-height 9:16 vertical video player embedded with SharedVlcPlayer, seamless video looping,
debounced gesture/scroll navigation, action sidebar with optimistic likes and comments modal,
creator info with follow action, and watch time telemetry (POST /api/media/{id}/view).

API Calls:
- GET /api/reels?size=5&exclude=... -> {items: MediaCard[], hasNext}
- POST /api/media/{id}/view {watchMs, durationMs, completed} -> 204
- POST /api/media/{id}/like, DELETE /api/media/{id}/like
- POST /api/media/{id}/share -> {shareCount, shareUrl}
- DELETE /api/media/{id} -> 204
- POST /api/users/{id}/follow, DELETE /api/users/{id}/follow
"""

import logging
import time
from typing import Any, Callable, Dict, List, Optional, Set

from ..async_utils import run_async
from ..cache import load_image_async
from ..theme import (
    get_theme_colors,
    font_body,
    font_caption,
    font_h2,
    RADIUS_BUTTON,
    RADIUS_CARD,
)
from ..widgets import AvatarView, ConfirmDialog, Toast
from .comments import CommentsModal

from ..theme import UI_FONT
from ..anim import pop_button

logger = logging.getLogger("SocialApp.screens.reels")

_HAS_CTK = False
try:
    import customtkinter as ctk
    _HAS_CTK = True
except Exception:
    ctk = None
    _HAS_CTK = False

_FrameBase = ctk.CTkFrame if _HAS_CTK else object


class ReelsScreen(_FrameBase):
    """
    Vertical Reels feed with shared VLC video playback, gesture navigation, and recommendation telemetry.
    """

    DEBOUNCE_MS = 450

    def __init__(
        self,
        master: Any,
        app_state: Any = None,
        on_user_click: Optional[Callable[[int], None]] = None,
        mode: str = "dark",
        **kwargs: Any
    ) -> None:
        self.app_state = app_state
        self.on_user_click = on_user_click
        self.mode = mode

        self.reels: List[Dict[str, Any]] = []
        self.loaded_ids: List[int] = []
        self.current_idx = 0
        self.is_loading = False
        self.has_next = True
        self._last_nav_time = 0.0

        # Telemetry tracking for active reel
        self._reel_start_time = 0.0
        self._accumulated_watch_ms = 0
        self._has_looped = False
        self._is_muted = False
        self._caption_expanded = False

        if _HAS_CTK:
            super().__init__(master, fg_color="#000000", **kwargs)
            self._build_ui()
            self._bind_navigation()
        else:
            self._frame = None

    def _build_ui(self) -> None:
        if not _HAS_CTK:
            return

        colors = get_theme_colors(self.mode)

        # 9:16 Video Player Container filling full available height
        self._player_frame = ctk.CTkFrame(
            self,
            fg_color="#000000",
            corner_radius=0
        )
        self._player_frame.pack(fill="both", expand=True)

        # Thumbnail canvas overlay (shown while loading)
        self._thumbnail_label = ctk.CTkLabel(
            self._player_frame,
            text="",
            fg_color="#000000"
        )
        self._thumbnail_label.place(relx=0, rely=0, relwidth=1.0, relheight=1.0)

        # Large Play/Pause Toggle Indicator
        self._play_indicator = ctk.CTkLabel(
            self._player_frame,
            text="▶",
            width=72,
            height=72,
            corner_radius=36,
            fg_color="#1A1A1A",
            font=(UI_FONT, 28, "bold"),
            text_color="#FFFFFF"
        )

        # Top Bar Overlays: Pause/Play & Mute toggle buttons (top right)
        self._pause_btn = ctk.CTkButton(
            self._player_frame,
            text="❚❚",
            width=36,
            height=36,
            font=(UI_FONT, 14, "bold"),
            fg_color="#1A1A1A",
            hover_color="#333333",
            border_width=1,
            border_color="#333333",
            corner_radius=18,
            command=self._toggle_play_pause
        )
        self._pause_btn.place(relx=0.82, rely=0.04, anchor="ne")

        self._mute_btn = ctk.CTkButton(
            self._player_frame,
            text="🔊",
            width=36,
            height=36,
            font=(UI_FONT, 16),
            fg_color="#1A1A1A",
            hover_color="#333333",
            border_width=1,
            border_color="#333333",
            corner_radius=18,
            command=self._toggle_mute
        )
        self._mute_btn.place(relx=0.92, rely=0.04, anchor="ne")

        # Bottom Thin Progress Bar
        self._progress_bar = ctk.CTkProgressBar(
            self._player_frame,
            height=2,
            corner_radius=1,
            fg_color="#444444",
            progress_color="#FFFFFF"
        )
        self._progress_bar.set(0)
        self._progress_bar.place(relx=0, rely=0.995, relwidth=1.0, anchor="sw")

        # Bottom-Left Overlay: Creator info & caption
        self._info_overlay = ctk.CTkFrame(
            self._player_frame,
            fg_color="transparent"
        )
        self._info_overlay.place(relx=0.04, rely=0.96, relwidth=0.75, anchor="sw")

        # Creator row: Avatar, Username, Follow button
        creator_row = ctk.CTkFrame(self._info_overlay, fg_color="transparent")
        creator_row.pack(fill="x", anchor="w", pady=(0, 6))

        self._avatar = AvatarView(creator_row, size=38, command=self._on_creator_avatar_clicked)
        self._avatar.pack(side="left", padx=(0, 8))

        self._username_lbl = ctk.CTkLabel(
            creator_row,
            text="",
            font=font_body(bold=True),
            text_color="#FFFFFF",
            cursor="hand2"
        )
        self._username_lbl.pack(side="left", padx=(0, 8))
        self._username_lbl.bind("<Button-1>", lambda e: self._on_creator_avatar_clicked())

        self._follow_btn = ctk.CTkButton(
            creator_row,
            text="Follow",
            width=76,
            height=26,
            corner_radius=RADIUS_BUTTON,
            font=font_caption(bold=True),
            fg_color="#0095F6",
            hover_color="#1877F2",
            text_color="#FFFFFF",
            command=self._toggle_follow_creator
        )
        self._follow_btn.pack(side="left")

        # Caption label
        self._caption_lbl = ctk.CTkLabel(
            self._info_overlay,
            text="",
            font=font_body(),
            text_color="#FFFFFF",
            anchor="w",
            justify="left",
            wraplength=300,
            cursor="hand2"
        )
        self._caption_lbl.pack(fill="x", anchor="w")
        self._caption_lbl.bind("<Button-1>", lambda e: self._toggle_caption_expand())

        # Right-side Action Sidebar: Heart, Comment, Share, More
        self._sidebar = ctk.CTkFrame(self._player_frame, fg_color="transparent")
        self._sidebar.place(relx=0.95, rely=0.75, anchor="e")

        # 1. Like button + count
        self._like_btn = ctk.CTkButton(
            self._sidebar,
            text="♡",
            width=42,
            height=42,
            font=(UI_FONT, 22, "bold"),
            fg_color="transparent",
            hover_color="#262626",
            text_color="#FFFFFF",
            command=self._toggle_like
        )
        self._like_btn.pack(pady=(4, 0))

        self._like_count_lbl = ctk.CTkLabel(
            self._sidebar,
            text="0",
            font=font_caption(bold=True),
            text_color="#FFFFFF"
        )
        self._like_count_lbl.pack(pady=(0, 8))

        # 2. Comment button + count
        self._comment_btn = ctk.CTkButton(
            self._sidebar,
            text="💬",
            width=42,
            height=42,
            font=(UI_FONT, 20),
            fg_color="transparent",
            hover_color="#262626",
            text_color="#FFFFFF",
            command=self._open_comments
        )
        self._comment_btn.pack(pady=(0, 0))

        self._comment_count_lbl = ctk.CTkLabel(
            self._sidebar,
            text="0",
            font=font_caption(bold=True),
            text_color="#FFFFFF"
        )
        self._comment_count_lbl.pack(pady=(0, 8))

        # 3. Share button
        self._share_btn = ctk.CTkButton(
            self._sidebar,
            text="↗",
            width=42,
            height=42,
            font=(UI_FONT, 20),
            fg_color="transparent",
            hover_color="#262626",
            text_color="#FFFFFF",
            command=self._share_reel
        )
        self._share_btn.pack(pady=(0, 8))

        # 4. More Options button "•••"
        self._more_btn = ctk.CTkButton(
            self._sidebar,
            text="•••",
            width=42,
            height=42,
            font=(UI_FONT, 16, "bold"),
            fg_color="transparent",
            hover_color="#262626",
            text_color="#FFFFFF",
            command=self._open_more_options
        )
        self._more_btn.pack(pady=(0, 4))

        # End of feed banner (hidden initially)
        self._caught_up_lbl = ctk.CTkLabel(
            self._player_frame,
            text="You're all caught up! 🎉",
            font=font_h2(),
            text_color="#FFFFFF"
        )

    def _bind_navigation(self) -> None:
        if not _HAS_CTK:
            return

        # Up / Down arrows
        self.bind("<Down>", lambda e: self._nav_next())
        self.bind("<Up>", lambda e: self._nav_prev())

        # Mouse wheel (Windows / macOS / Linux)
        self._player_frame.bind("<MouseWheel>", self._on_mousewheel)
        self._player_frame.bind("<Button-4>", lambda e: self._nav_prev())
        self._player_frame.bind("<Button-5>", lambda e: self._nav_next())

        # Click video to play/pause
        self._thumbnail_label.bind("<Button-1>", lambda e: self._toggle_play_pause())
        self._player_frame.bind("<Button-1>", lambda e: self._toggle_play_pause())

    def _on_mousewheel(self, event: Any) -> None:
        delta = getattr(event, "delta", 0)
        if delta < 0:
            self._nav_next()
        elif delta > 0:
            self._nav_prev()

    def _nav_next(self) -> None:
        now = time.time()
        if (now - self._last_nav_time) < (self.DEBOUNCE_MS / 1000.0):
            return
        self._last_nav_time = now

        if self.current_idx + 1 < len(self.reels):
            self._flush_telemetry()
            self.current_idx += 1
            self._display_current_reel()

            # Preload more reels if at 2nd-to-last
            if self.current_idx >= len(self.reels) - 2 and self.has_next and not self.is_loading:
                self._fetch_reels()
        elif not self.has_next:
            if _HAS_CTK and hasattr(self, "_caught_up_lbl"):
                self._caught_up_lbl.place(relx=0.5, rely=0.5, anchor="center")

    def _nav_prev(self) -> None:
        now = time.time()
        if (now - self._last_nav_time) < (self.DEBOUNCE_MS / 1000.0):
            return
        self._last_nav_time = now

        if self.current_idx > 0:
            self._flush_telemetry()
            self.current_idx -= 1
            if _HAS_CTK and hasattr(self, "_caught_up_lbl"):
                self._caught_up_lbl.place_forget()
            self._display_current_reel()

    def _fetch_reels(self) -> None:
        api = self.app_state.api if self.app_state else None
        if not api or self.is_loading or not self.has_next:
            return
        self.is_loading = True

        exclude = list(self.loaded_ids)[-100:]

        def worker() -> Dict[str, Any]:
            return api.get_reels(size=5, exclude=exclude)

        def on_success(res: Dict[str, Any]) -> None:
            self.is_loading = False
            items = res.get("items", [])
            self.has_next = res.get("hasNext", False)

            for item in items:
                mid = item.get("id")
                if mid not in self.loaded_ids:
                    self.loaded_ids.append(mid)
                    self.reels.append(item)

            # If this is the initial load, display reel 0
            if items and len(self.reels) == len(items):
                self._display_current_reel()

        def on_error(exc: Exception) -> None:
            self.is_loading = False
            logger.warning("Failed to fetch reels: %s", exc)

        run_async(worker, on_success=on_success, on_error=on_error)

    def _get_current_reel(self) -> Optional[Dict[str, Any]]:
        if not self.reels or self.current_idx >= len(self.reels):
            return None
        return self.reels[self.current_idx]

    def _display_current_reel(self) -> None:
        reel = self._get_current_reel()
        if not reel:
            return

        # Reset telemetry counters
        self._reel_start_time = time.time()
        self._accumulated_watch_ms = 0
        self._has_looped = False
        self._caption_expanded = False

        user = reel.get("user", {})
        author_id = user.get("id", 0)
        username = user.get("username", "user")
        avatar_url = user.get("avatarUrl", "")
        caption = reel.get("caption", "")
        media_url = reel.get("mediaUrl", "")
        thumb_url = reel.get("thumbnailUrl") or media_url
        likes = int(reel.get("likeCount", 0))
        comments = int(reel.get("commentCount", 0))
        liked_by_me = bool(reel.get("likedByMe", False))

        if not _HAS_CTK:
            return

        # Update overlay text
        self._username_lbl.configure(text=f"@{username}")
        self._avatar.set_image(avatar_url)

        # Truncate caption
        short_caption = caption if len(caption) <= 75 else f"{caption[:73]}… more"
        self._caption_lbl.configure(text=short_caption)

        # Update like & comment counts
        self._like_btn.configure(
            text="♥" if liked_by_me else "♡",
            text_color="#FF3040" if liked_by_me else "#FFFFFF"
        )
        self._like_count_lbl.configure(text=str(likes))
        self._comment_count_lbl.configure(text=str(comments))

        # Check follow button (hide if own reel)
        me_id = getattr(self.app_state.api, "_current_user_id", None) if self.app_state else None
        if author_id == me_id:
            self._follow_btn.pack_forget()
        else:
            self._follow_btn.pack(side="left")
            followed = bool(user.get("followedByMe", False))
            self._follow_btn.configure(
                text="Following" if followed else "Follow",
                fg_color="#333333" if followed else "#0095F6"
            )

        # Show thumbnail while video is loading
        def on_thumb_ready(wrapped: Any) -> None:
            try:
                self._thumbnail_label.configure(image=wrapped)
            except Exception:
                pass

        placeholder = load_image_async(thumb_url, (440, 780), on_ready=on_thumb_ready)
        self._thumbnail_label.configure(image=placeholder)
        self._thumbnail_label.place(relx=0, rely=0, relwidth=1.0, relheight=1.0)
        if hasattr(self._player_frame, "_canvas"):
            self._thumbnail_label.lift(self._player_frame._canvas)

        # Stop previous playback and play current video
        player = self.app_state.player if self.app_state else None
        if player:
            player.stop()
            self._player_frame.update_idletasks()
            player.play_url(media_url, widget=self._player_frame, loop=True)
            if self._is_muted:
                player.mute()
            else:
                player.unmute()

        if hasattr(self, "_pause_btn"):
            self._pause_btn.configure(text="❚❚")
        if hasattr(self, "_play_indicator"):
            self._play_indicator.place_forget()

        # Hide thumbnail after short buffer and start progress bar ticker
        self.after(200, lambda: self._thumbnail_label.place_forget())
        self._start_progress_ticker()

    def _start_progress_ticker(self) -> None:
        if getattr(self, "_prog_timer_id", None) is not None:
            try:
                self.after_cancel(self._prog_timer_id)
            except Exception:
                pass
            self._prog_timer_id = None
        self._tick_progress()

    def _tick_progress(self) -> None:
        if not _HAS_CTK or not self.winfo_exists():
            return
        player = self.app_state.player if self.app_state else None
        if player and hasattr(self, "_progress_bar"):
            try:
                dur = player.get_length() or 5000
                cur = player.get_time() or 0
                if dur > 0:
                    self._progress_bar.set(max(0.0, min(1.0, (cur % dur) / dur)))
            except Exception:
                pass
        self._prog_timer_id = self.after(80, self._tick_progress)

    def _toggle_play_pause(self) -> None:
        player = self.app_state.player if self.app_state else None
        if not player or not _HAS_CTK:
            return

        if player.is_playing():
            player.pause()
            self._play_indicator.configure(text="❚❚")
            if hasattr(self, "_pause_btn"):
                self._pause_btn.configure(text="▶")
            self._play_indicator.place(relx=0.5, rely=0.5, anchor="center")
            self._play_indicator.lift()
        else:
            player.resume()
            self._play_indicator.configure(text="▶")
            if hasattr(self, "_pause_btn"):
                self._pause_btn.configure(text="❚❚")
            self._play_indicator.place(relx=0.5, rely=0.5, anchor="center")
            self._play_indicator.lift()
            self.after(450, lambda: self._play_indicator.place_forget() if player.is_playing() else None)

    def _toggle_mute(self) -> None:
        self._is_muted = not self._is_muted
        player = self.app_state.player if self.app_state else None
        if player:
            if self._is_muted:
                player.mute()
            else:
                player.unmute()
        if _HAS_CTK and hasattr(self, "_mute_btn"):
            self._mute_btn.configure(text="🔇" if self._is_muted else "🔊")

    def _toggle_caption_expand(self) -> None:
        reel = self._get_current_reel()
        if not reel or not _HAS_CTK:
            return
        caption = reel.get("caption", "")
        self._caption_expanded = not self._caption_expanded
        if self._caption_expanded:
            self._caption_lbl.configure(text=caption)
        else:
            short_c = caption if len(caption) <= 75 else f"{caption[:73]}… more"
            self._caption_lbl.configure(text=short_c)

    def _toggle_like(self) -> None:
        reel = self._get_current_reel()
        if not reel or not self.app_state or not self.app_state.api:
            return

        media_id = reel.get("id", 0)
        liked = bool(reel.get("likedByMe", False))
        count = int(reel.get("likeCount", 0))

        # Optimistic update
        reel["likedByMe"] = not liked
        reel["likeCount"] = count + (1 if not liked else -1)

        if _HAS_CTK:
            self._like_btn.configure(
                text="♥" if reel["likedByMe"] else "♡",
                text_color="#FF3040" if reel["likedByMe"] else "#FFFFFF"
            )
            self._like_count_lbl.configure(text=str(reel["likeCount"]))
            if reel["likedByMe"]:
                pop_button(self._like_btn, 22, UI_FONT)

        api = self.app_state.api

        def worker() -> None:
            if not liked:
                api.like_media(media_id)
            else:
                api.unlike_media(media_id)

        def on_error(exc: Exception) -> None:
            # Revert on failure
            reel["likedByMe"] = liked
            reel["likeCount"] = count
            if _HAS_CTK:
                self._like_btn.configure(
                    text="♥" if liked else "♡",
                    text_color="#FF3040" if liked else "#FFFFFF"
                )
                self._like_count_lbl.configure(text=str(count))

        run_async(worker, on_error=on_error)

    def _toggle_follow_creator(self) -> None:
        reel = self._get_current_reel()
        if not reel or not self.app_state or not self.app_state.api:
            return

        user = reel.get("user", {})
        uid = user.get("id", 0)
        followed = bool(user.get("followedByMe", False))
        api = self.app_state.api

        def worker() -> Dict[str, Any]:
            if followed:
                return api.unfollow_user(uid)
            else:
                return api.follow_user(uid)

        def on_success(res: Dict[str, Any]) -> None:
            user["followedByMe"] = res.get("following", False)
            if _HAS_CTK:
                self._follow_btn.configure(
                    text="Following" if user["followedByMe"] else "Follow",
                    fg_color="#333333" if user["followedByMe"] else "#0095F6"
                )

        run_async(worker, on_success=on_success)

    def _open_comments(self) -> None:
        reel = self._get_current_reel()
        if not reel or not _HAS_CTK:
            return
        api = self.app_state.api if self.app_state else None
        media_id = reel.get("id", 0)

        def on_count_changed(new_count: int) -> None:
            reel["commentCount"] = new_count
            self._comment_count_lbl.configure(text=str(new_count))

        CommentsModal(
            parent=self.winfo_toplevel(),
            media_id=media_id,
            api=api,
            on_comment_count_change=on_count_changed,
            mode=self.mode
        )

    def _share_reel(self) -> None:
        reel = self._get_current_reel()
        if not reel or not self.app_state or not self.app_state.api:
            return
        media_id = reel.get("id", 0)
        try:
            res = self.app_state.api.share_media(media_id)
            share_url = res.get("shareUrl", f"http://localhost:8080/m/{media_id}")
            if _HAS_CTK:
                self.clipboard_clear()
                self.clipboard_append(share_url)
                Toast.show(self.winfo_toplevel(), "Reel link copied!")
        except Exception as e:
            logger.warning("Share reel error: %s", e)

    def _open_more_options(self) -> None:
        reel = self._get_current_reel()
        if not reel or not _HAS_CTK:
            return

        author_id = reel.get("user", {}).get("id", 0)
        me_id = getattr(self.app_state.api, "_current_user_id", None) if self.app_state else None

        if author_id == me_id:
            # Own reel: Delete option
            ConfirmDialog(
                self.winfo_toplevel(),
                title="Delete Reel",
                message="Delete this reel? This cannot be undone.",
                confirm_text="Delete",
                on_confirm=self._delete_current_reel
            )
        else:
            # Other's reel: "Not interested" option
            ConfirmDialog(
                self.winfo_toplevel(),
                title="Reel Options",
                message="Choose an action for this reel:",
                confirm_text="Not Interested",
                cancel_text="Cancel",
                on_confirm=self._mark_not_interested
            )

    def _delete_current_reel(self) -> None:
        reel = self._get_current_reel()
        if not reel or not self.app_state or not self.app_state.api:
            return
        media_id = reel.get("id", 0)

        def worker() -> None:
            self.app_state.api.delete_media(media_id)

        def on_success(_: Any) -> None:
            Toast.show(self.winfo_toplevel(), "Reel deleted.")
            self.reels.pop(self.current_idx)
            if self.current_idx >= len(self.reels):
                self.current_idx = max(0, len(self.reels) - 1)
            self._display_current_reel()

        run_async(worker, on_success=on_success)

    def _mark_not_interested(self) -> None:
        reel = self._get_current_reel()
        if not reel or not self.app_state or not self.app_state.api:
            return
        media_id = reel.get("id", 0)

        # Send telemetry with watchMs = 0
        run_async(lambda: self.app_state.api.send_view_telemetry(media_id, watch_ms=0, duration_ms=10000, completed=False))

        # Advance to next reel and remove from list
        self.reels.pop(self.current_idx)
        if self.current_idx >= len(self.reels):
            self.current_idx = max(0, len(self.reels) - 1)
        self._display_current_reel()

    def _flush_telemetry(self) -> None:
        """Send watch time telemetry for the currently viewed reel."""
        reel = self._get_current_reel()
        if not reel or not self.app_state or not self.app_state.api:
            return

        media_id = reel.get("id", 0)
        player = self.app_state.player

        # Calculate watch duration
        now = time.time()
        elapsed_sec = max(0.0, now - self._reel_start_time)
        watch_ms = int(elapsed_sec * 1000)

        duration_ms = 10000
        if player:
            try:
                p_len = player.get_length()
                if p_len and p_len > 0:
                    duration_ms = p_len
            except Exception:
                pass

        completed = (watch_ms >= int(duration_ms * 0.8)) or self._has_looped
        api = self.app_state.api

        run_async(lambda: api.send_view_telemetry(
            media_id=media_id,
            watch_ms=watch_ms,
            duration_ms=duration_ms,
            completed=completed
        ))

    def _on_creator_avatar_clicked(self) -> None:
        reel = self._get_current_reel()
        if not reel:
            return
        uid = reel.get("user", {}).get("id", 0)
        if self.on_user_click:
            self.on_user_click(uid)
        elif self.app_state and self.app_state.router:
            from .profile import ProfileScreen
            self.app_state.router.push(
                ProfileScreen,
                title="Profile",
                app_state=self.app_state,
                user_id=uid,
                mode=self.mode
            )

    def on_enter(self, **kwargs: Any) -> None:
        """Screen entered: start or resume playback."""
        if not self.reels:
            self._fetch_reels()
        else:
            self._display_current_reel()

    def on_leave(self) -> None:
        """Screen left: stop player and send telemetry."""
        self._flush_telemetry()
        if self.app_state and self.app_state.player:
            try:
                self.app_state.player.stop()
            except Exception:
                pass
