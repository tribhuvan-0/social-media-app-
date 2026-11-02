"""
Reusable CustomTkinter components for SocialApp:
- AvatarView: circular avatar with LRU caching and click callback
- StoryRing: avatar enclosed in dynamic unread gradient / seen grey ring
- PostCard: Instagram post card with header, media canvas, optimistic likes, caption, comments
- UserRow: user summary row with avatar, bold username, and Follow / Following / Requested button
- Toast: ephemeral top-sliding notification banner
- ConfirmDialog: modal confirmation dialog for destructive actions
- LoadingSpinner: lightweight animated or static loading indicator
"""

from datetime import datetime, timezone
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageOps

from .cache import load_image_async, get_placeholder_image, wrap_image
from .theme import get_color, get_theme_colors, font_body, font_caption, font_small, font_h2, RADIUS_BUTTON, RADIUS_CARD

from .theme import UI_FONT
from .anim import fade_in_window, pop_button, slide_down_toast, slide_up_dismiss

logger = logging.getLogger("SocialApp.widgets")

# Detect CustomTkinter availability
_HAS_CTK = False
try:
    import customtkinter as ctk
    import tkinter as tk
    _HAS_CTK = True
except Exception:
    ctk = None
    tk = None
    _HAS_CTK = False

# Base class shims for headless/non-CTk environments
_FrameBase = ctk.CTkFrame if _HAS_CTK else object
_LabelBase = ctk.CTkLabel if _HAS_CTK else object
_ButtonBase = ctk.CTkButton if _HAS_CTK else object
_ToplevelBase = ctk.CTkToplevel if _HAS_CTK else object


def format_relative_time(iso_str: str) -> str:
    """Format ISO-8601 UTC timestamp to relative Instagram format ('5m', '3h', '2d', etc.)."""
    if not iso_str:
        return ""
    try:
        # Normalize trailing Z
        cleaned = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        now = datetime.now(timezone.utc)
        diff = now - dt
        seconds = int(diff.total_seconds())
        if seconds < 60:
            return f"{max(1, seconds)}s"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h"
        days = hours // 24
        if days < 7:
            return f"{days}d"
        return dt.strftime("%b %d")
    except Exception:
        return iso_str[:10]


class AvatarView(_FrameBase):
    """
    Circular avatar component with async dual-tier caching.
    Supports customizable diameter and click handling.
    """

    def __init__(
        self,
        master: Any,
        image_url_or_path: str = "",
        size: int = 36,
        command: Optional[Callable[[], None]] = None,
        fg_color: str = "transparent",
        **kwargs: Any
    ) -> None:
        if _HAS_CTK:
            super().__init__(master, width=size, height=size, fg_color=fg_color, **kwargs)
            self._size = size
            self._command = command
            self._img_label = ctk.CTkLabel(self, text="", width=size, height=size)
            self._img_label.pack(fill="both", expand=True)

            if command:
                self._img_label.bind("<Button-1>", lambda e: self._command())
                self.bind("<Button-1>", lambda e: self._command())

            self.set_image(image_url_or_path)
        else:
            self._size = size
            self._command = command

    def set_image(self, url_or_path: str) -> None:
        if not _HAS_CTK:
            return

        def on_loaded(wrapped_img):
            try:
                self._img_label.configure(image=wrapped_img)
            except Exception:
                pass

        placeholder = load_image_async(
            url_or_path,
            (self._size, self._size),
            is_circular=True,
            on_ready=on_loaded
        )
        self._img_label.configure(image=placeholder)


class StoryRing(_FrameBase):
    """
    Circular avatar enclosed by an Instagram story gradient ring (unread)
    or muted grey ring (seen).
    """

    def __init__(
        self,
        master: Any,
        avatar_url: str = "",
        username: str = "",
        has_unseen: bool = True,
        size: int = 64,
        command: Optional[Callable[[], None]] = None,
        is_my_story: bool = False,
        mode: str = "dark",
        **kwargs: Any
    ) -> None:
        if _HAS_CTK:
            super().__init__(master, fg_color="transparent", **kwargs)
            self._command = command
            self._size = size
            self._mode = mode
            ring_thickness = 3
            outer_size = size + (ring_thickness * 2) + 4
            inner_avatar_size = size

            # Ring container
            self._ring_frame = ctk.CTkFrame(
                self,
                width=outer_size,
                height=outer_size,
                corner_radius=outer_size // 2,
                fg_color=self._get_ring_color(has_unseen)
            )
            self._ring_frame.pack(padx=2, pady=(2, 0))

            # Inner background padding to create separation ring
            colors = get_theme_colors(mode)
            self._inner_pad = ctk.CTkFrame(
                self._ring_frame,
                width=outer_size - 4,
                height=outer_size - 4,
                corner_radius=(outer_size - 4) // 2,
                fg_color=colors["bg"]
            )
            self._inner_pad.place(relx=0.5, rely=0.5, anchor="center")

            # Avatar
            self._avatar = AvatarView(
                self._inner_pad,
                image_url_or_path=avatar_url,
                size=inner_avatar_size,
                command=command
            )
            self._avatar.place(relx=0.5, rely=0.5, anchor="center")

            # Username label (truncated to 10 chars)
            display_name = username if len(username) <= 10 else f"{username[:9]}…"
            if is_my_story and not username:
                display_name = "Your story"
            self._name_label = ctk.CTkLabel(
                self,
                text=display_name,
                font=font_small(),
                text_color=colors["text_primary"]
            )
            self._name_label.pack(pady=(2, 2))

            if command:
                self._name_label.bind("<Button-1>", lambda e: self._command())
                self._ring_frame.bind("<Button-1>", lambda e: self._command())
        else:
            self._command = command

    def _get_ring_color(self, has_unseen: bool) -> str:
        colors = get_theme_colors(self._mode)
        if has_unseen:
            # Dominant Instagram pink/purple gradient color
            return "#EE2A7B"
        return str(colors.get("story_ring_seen", "#3A3A3A"))

    def set_seen(self, is_seen: bool) -> None:
        if _HAS_CTK and hasattr(self, "_ring_frame"):
            self._ring_frame.configure(fg_color=self._get_ring_color(not is_seen))


_active_post_card: Any = None


class PostCard(_FrameBase):
    """
    Standard Instagram Post card:
    - Author header: avatar, bold username, timestamp, options menu
    - 440x440 media container (image or video thumbnail with play button)
    - Action row: heart (like toggle), comment bubble, share/link
    - Like count
    - Expandable caption
    - Comment launcher
    """

    def __init__(
        self,
        master: Any,
        media_data: Dict[str, Any],
        api: Any,
        player: Any,
        on_user_click: Optional[Callable[[int], None]] = None,
        on_comment_click: Optional[Callable[[int], None]] = None,
        on_delete_success: Optional[Callable[[int], None]] = None,
        mode: str = "dark",
        **kwargs: Any
    ) -> None:
        if _HAS_CTK:
            colors = get_theme_colors(mode)
            super().__init__(
                master,
                fg_color=colors["card"],
                border_width=1,
                border_color=colors["border"],
                corner_radius=RADIUS_CARD,
                **kwargs
            )
            self._media = media_data
            self._api = api
            self._player = player
            self._on_user_click = on_user_click
            self._on_comment_click = on_comment_click
            self._on_delete_success = on_delete_success
            self._mode = mode
            self._liked = bool(media_data.get("likedByMe", False))
            self._like_count = int(media_data.get("likeCount", 0))
            self._comment_count = int(media_data.get("commentCount", 0))
            self._caption_expanded = False

            self._build_ui()
        else:
            self._media = media_data

    def _build_ui(self) -> None:
        colors = get_theme_colors(self._mode)
        user = self._media.get("user", {})
        author_id = user.get("id", 0)
        username = user.get("username", "user")
        avatar_url = user.get("avatarUrl", "")

        # 1. Header Frame
        header = ctk.CTkFrame(self, fg_color="transparent", height=44)
        header.pack(fill="x", padx=8, pady=(8, 4))

        # Avatar
        avatar = AvatarView(
            header,
            image_url_or_path=avatar_url,
            size=36,
            command=lambda: self._handle_user_click(author_id)
        )
        avatar.pack(side="left", padx=(0, 8))

        # Username & Time
        user_frame = ctk.CTkFrame(header, fg_color="transparent")
        user_frame.pack(side="left", fill="y", expand=True)

        user_btn = ctk.CTkLabel(
            user_frame,
            text=username,
            font=font_body(bold=True),
            text_color=colors["text_primary"],
            cursor="hand2"
        )
        user_btn.pack(side="left")
        user_btn.bind("<Button-1>", lambda e: self._handle_user_click(author_id))

        time_str = format_relative_time(self._media.get("createdAt", ""))
        time_label = ctk.CTkLabel(
            user_frame,
            text=f" • {time_str}",
            font=font_caption(),
            text_color=colors["text_muted"]
        )
        time_label.pack(side="left")

        # More menu button "..."
        more_btn = ctk.CTkButton(
            header,
            text="•••",
            width=30,
            height=30,
            fg_color="transparent",
            text_color=colors["text_muted"],
            hover_color=colors["surface_elevated"],
            command=self._open_more_menu
        )
        more_btn.pack(side="right")

        # 2. Media Area (440x440)
        self._media_frame = ctk.CTkFrame(
            self,
            width=440,
            height=440,
            corner_radius=8,
            fg_color=colors["surface"]
        )
        self._media_frame.pack(fill="x", padx=4, pady=4)
        self._media_frame.pack_propagate(False)

        # Image/Thumbnail Canvas
        self._media_label = ctk.CTkLabel(self._media_frame, text="")
        self._media_label.pack(fill="both", expand=True)

        thumb_url = self._media.get("thumbnailUrl") or self._media.get("mediaUrl", "")
        self._load_thumbnail(thumb_url)

        # Video overlay indicator
        if self._media.get("mediaKind") == "VIDEO":
            self._play_btn = ctk.CTkButton(
                self._media_frame,
                text="▶",
                font=(UI_FONT, 24, "bold"),
                width=60,
                height=60,
                corner_radius=30,
                fg_color="#1A1A1A",
                hover_color="#333333",
                command=self._play_video
            )
            self._play_btn.place(relx=0.5, rely=0.5, anchor="center")

            # In-video controls (created before the video surface so they stay on top)
            self._pause_ctrl_btn = ctk.CTkButton(
                self._media_frame,
                text="❚❚",
                width=34,
                height=34,
                corner_radius=17,
                font=(UI_FONT, 13, "bold"),
                fg_color="#1A1A1A",
                hover_color="#333333",
                border_width=1,
                border_color="#333333",
                text_color="#FFFFFF",
                command=self._on_video_click
            )
            self._mute_btn = ctk.CTkButton(
                self._media_frame,
                text="🔊",
                width=34,
                height=34,
                corner_radius=17,
                font=(UI_FONT, 15),
                fg_color="#1A1A1A",
                hover_color="#333333",
                border_width=1,
                border_color="#333333",
                text_color="#FFFFFF",
                command=self._toggle_mute
            )
            self._pause_ind = ctk.CTkLabel(
                self._media_frame,
                text="❚❚",
                width=64,
                height=64,
                corner_radius=32,
                font=(UI_FONT, 22, "bold"),
                fg_color="#1A1A1A",
                text_color="#FFFFFF"
            )
            # Click anywhere on the video toggles pause / replays when stopped
            self._media_frame.bind("<Button-1>", lambda e: self._on_video_click())

        # Double click to like
        self._media_label.bind("<Double-Button-1>", lambda e: self._on_double_click_like())

        # 3. Action Bar (Heart, Comment, Share)
        action_bar = ctk.CTkFrame(self, fg_color="transparent", height=36)
        action_bar.pack(fill="x", padx=8, pady=4)

        # Heart like button
        self._like_btn = ctk.CTkButton(
            action_bar,
            text="♥" if self._liked else "♡",
            font=(UI_FONT, 18, "bold"),
            width=36,
            height=36,
            fg_color="transparent",
            text_color=colors["like_red"] if self._liked else colors["text_primary"],
            hover_color=colors["surface_elevated"],
            command=self._toggle_like
        )
        self._like_btn.pack(side="left", padx=(0, 4))

        # Comment bubble button
        comment_btn = ctk.CTkButton(
            action_bar,
            text="💬",
            font=(UI_FONT, 16),
            width=36,
            height=36,
            fg_color="transparent",
            text_color=colors["text_primary"],
            hover_color=colors["surface_elevated"],
            command=self._handle_comment_click
        )
        comment_btn.pack(side="left", padx=(0, 4))

        # Share button
        share_btn = ctk.CTkButton(
            action_bar,
            text="↗",
            font=(UI_FONT, 16),
            width=36,
            height=36,
            fg_color="transparent",
            text_color=colors["text_primary"],
            hover_color=colors["surface_elevated"],
            command=self._share_post
        )
        share_btn.pack(side="left")

        # 4. Likes Count
        self._likes_label = ctk.CTkLabel(
            self,
            text=f"{self._like_count} likes",
            font=font_body(bold=True),
            text_color=colors["text_primary"],
            anchor="w"
        )
        self._likes_label.pack(fill="x", padx=12, pady=(0, 2))

        # 5. Caption
        caption_text = self._media.get("caption", "")
        if caption_text:
            self._caption_frame = ctk.CTkFrame(self, fg_color="transparent")
            self._caption_frame.pack(fill="x", padx=12, pady=(0, 4))

            full_text = f"{username}  {caption_text}"
            short_text = full_text if len(full_text) <= 90 else f"{full_text[:88]}… more"

            self._caption_label = ctk.CTkLabel(
                self._caption_frame,
                text=short_text,
                font=font_body(bold=False),
                text_color=colors["text_primary"],
                anchor="w",
                justify="left",
                wraplength=440
            )
            self._caption_label.pack(side="left", fill="x", expand=True)

            if len(full_text) > 90:
                self._caption_label.bind("<Button-1>", lambda e: self._toggle_caption(full_text, short_text))

        # 6. Comments Link
        if self._comment_count > 0:
            comments_text = f"View all {self._comment_count} comments"
        else:
            comments_text = "Add a comment…"

        self._comments_link = ctk.CTkLabel(
            self,
            text=comments_text,
            font=font_caption(),
            text_color=colors["text_muted"],
            anchor="w",
            cursor="hand2"
        )
        self._comments_link.pack(fill="x", padx=12, pady=(0, 8))
        self._comments_link.bind("<Button-1>", lambda e: self._handle_comment_click())

        # Divider
        divider = ctk.CTkFrame(self, height=1, fg_color=colors["divider"])
        divider.pack(fill="x", pady=(4, 12))

    def _load_thumbnail(self, url_or_path: str) -> None:
        def on_ready(wrapped):
            try:
                self._media_label.configure(image=wrapped)
            except Exception:
                pass

        placeholder = load_image_async(
            url_or_path,
            (440, 440),
            is_circular=False,
            corner_radius=8,
            on_ready=on_ready
        )
        self._media_label.configure(image=placeholder)

    def _play_video(self) -> None:
        global _active_post_card
        if not self._player:
            return
        video_url = self._media.get("mediaUrl", "")
        if not video_url:
            return

        # Only one feed video plays at a time: restore the previous card's poster
        if _active_post_card is not None and _active_post_card is not self:
            try:
                _active_post_card._reset_video()
            except Exception:
                pass
        _active_post_card = self

        if hasattr(self, "_play_btn"):
            self._play_btn.place_forget()
        if hasattr(self, "_media_label"):
            self._media_label.pack_forget()

        self._player.stop()
        self._player.play_url(video_url, widget=self._media_frame, loop=True)
        if hasattr(self, "_pause_ctrl_btn"):
            self._pause_ctrl_btn.configure(text="❚❚")
            self._pause_ctrl_btn.place(relx=0.84, rely=0.05, anchor="ne")
            self._pause_ctrl_btn.lift()
        if hasattr(self, "_mute_btn"):
            muted = bool(getattr(self._player, "_is_muted", False))
            self._mute_btn.configure(text="🔇" if muted else "🔊")
            self._mute_btn.place(relx=0.95, rely=0.05, anchor="ne")
            self._mute_btn.lift()

    def _reset_video(self) -> None:
        """Return this card to its poster state (thumbnail + play button)."""
        try:
            if self._player and hasattr(self._player, "detach_surface"):
                self._player.detach_surface(self._media_frame)
            for name in ("_pause_ctrl_btn", "_mute_btn", "_pause_ind"):
                if hasattr(self, name):
                    getattr(self, name).place_forget()
            if hasattr(self, "_media_label"):
                self._media_label.pack(fill="both", expand=True)
            if hasattr(self, "_play_btn"):
                self._play_btn.place(relx=0.5, rely=0.5, anchor="center")
        except Exception:
            pass

    def _on_video_click(self) -> None:
        if not self._player or self._media.get("mediaKind") != "VIDEO":
            return
        active = getattr(self._player, "is_active_on", lambda w: False)(self._media_frame)
        if not active:
            self._play_video()
            return
        self._player.toggle_pause()
        playing = self._player.is_playing()
        if hasattr(self, "_pause_ctrl_btn"):
            self._pause_ctrl_btn.configure(text="❚❚" if playing else "▶")
            self._pause_ctrl_btn.lift()
        if hasattr(self, "_pause_ind"):
            self._pause_ind.configure(text="▶" if playing else "❚❚")
            self._pause_ind.place(relx=0.5, rely=0.5, anchor="center")
            self._pause_ind.lift()
            self.after(550, lambda: self._pause_ind.place_forget() if playing else None)

    def _toggle_mute(self) -> None:
        if not self._player:
            return
        muted = self._player.toggle_mute()
        if hasattr(self, "_mute_btn"):
            self._mute_btn.configure(text="🔇" if muted else "🔊")

    def _toggle_like(self) -> None:
        """Optimistic like toggle."""
        colors = get_theme_colors(self._mode)
        media_id = self._media.get("id", 0)
        previous_liked = self._liked
        previous_count = self._like_count

        # Instant optimistic update
        self._liked = not self._liked
        self._like_count += (1 if self._liked else -1)
        self._update_like_ui(colors)
        if self._liked:
            pop_button(self._like_btn, 18, UI_FONT)

        # Dispatch async call
        def on_err(exc):
            # Rollback on error
            self._liked = previous_liked
            self._like_count = previous_count
            self._update_like_ui(colors)
            logger.warning("Like toggle failed: %s", exc)

        if self._liked:
            self._api.like_media(media_id)
        else:
            self._api.unlike_media(media_id)

    def _on_double_click_like(self) -> None:
        if not self._liked:
            self._toggle_like()

    def _update_like_ui(self, colors: Dict[str, Any]) -> None:
        self._like_btn.configure(
            text="♥" if self._liked else "♡",
            text_color=colors["like_red"] if self._liked else colors["text_primary"]
        )
        self._likes_label.configure(text=f"{self._like_count} likes")

    def _toggle_caption(self, full_text: str, short_text: str) -> None:
        self._caption_expanded = not self._caption_expanded
        self._caption_label.configure(text=full_text if self._caption_expanded else short_text)

    def _share_post(self) -> None:
        media_id = self._media.get("id", 0)
        try:
            res = self._api.share_media(media_id)
            share_url = res.get("shareUrl", f"http://localhost:8080/m/{media_id}")
            # Copy to clipboard
            self.clipboard_clear()
            self.clipboard_append(share_url)
            Toast.show(self.winfo_toplevel(), "Link copied to clipboard!")
        except Exception as e:
            logger.warning("Share failed: %s", e)

    def _open_more_menu(self) -> None:
        # Options menu
        user = self._media.get("user", {})
        author_id = user.get("id", 0)
        me_id = getattr(self._api, "_current_user_id", None)

        dialog = ConfirmDialog(
            self.winfo_toplevel(),
            title="Post Options",
            message=f"Manage Post #{self._media.get('id')}",
            confirm_text="Delete Post" if author_id == me_id else "Copy Link",
            on_confirm=self._delete_or_copy
        )

    def _delete_or_copy(self) -> None:
        user = self._media.get("user", {})
        author_id = user.get("id", 0)
        me_id = getattr(self._api, "_current_user_id", None)
        media_id = self._media.get("id", 0)

        if author_id == me_id:
            try:
                self._api.delete_media(media_id)
                Toast.show(self.winfo_toplevel(), "Post deleted.")
                if self._on_delete_success:
                    self._on_delete_success(media_id)
                self.destroy()
            except Exception as e:
                Toast.show(self.winfo_toplevel(), f"Delete failed: {e}", toast_type="error")
        else:
            self._share_post()

    def _handle_user_click(self, user_id: int) -> None:
        if self._on_user_click:
            self._on_user_click(user_id)

    def _handle_comment_click(self) -> None:
        media_id = self._media.get("id", 0)
        if self._on_comment_click:
            self._on_comment_click(media_id)


class UserRow(_FrameBase):
    """
    User row displaying avatar, bold username, subtitle (name/bio),
    and an action Follow / Following / Requested button.
    """

    def __init__(
        self,
        master: Any,
        user_summary: Dict[str, Any],
        api: Any,
        on_click: Optional[Callable[[int], None]] = None,
        mode: str = "dark",
        **kwargs: Any
    ) -> None:
        if _HAS_CTK:
            super().__init__(master, fg_color="transparent", height=54, **kwargs)
            self._user = user_summary
            self._api = api
            self._on_click = on_click
            self._mode = mode
            self._followed = bool(user_summary.get("followedByMe", False))
            self._requested = bool(user_summary.get("requestedByMe", False))

            self._build_ui()
        else:
            self._user = user_summary

    def _build_ui(self) -> None:
        colors = get_theme_colors(self._mode)
        uid = self._user.get("id", 0)
        username = self._user.get("username", "user")
        avatar_url = self._user.get("avatarUrl", "")

        # Avatar
        self._avatar = AvatarView(
            self,
            image_url_or_path=avatar_url,
            size=44,
            command=lambda: self._handle_click(uid)
        )
        self._avatar.pack(side="left", padx=(8, 10), pady=4)

        # Name / Info frame
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.pack(side="left", fill="y", expand=True)

        name_lbl = ctk.CTkLabel(
            info_frame,
            text=username,
            font=font_body(bold=True),
            text_color=colors["text_primary"],
            anchor="w",
            cursor="hand2"
        )
        name_lbl.pack(fill="x", anchor="w")
        name_lbl.bind("<Button-1>", lambda e: self._handle_click(uid))

        sub_lbl = ctk.CTkLabel(
            info_frame,
            text="Suggested for you",
            font=font_caption(),
            text_color=colors["text_muted"],
            anchor="w"
        )
        sub_lbl.pack(fill="x", anchor="w")

        # Follow button
        self._btn = ctk.CTkButton(
            self,
            width=90,
            height=30,
            corner_radius=RADIUS_BUTTON,
            font=font_caption(bold=True),
            command=self._toggle_follow
        )
        self._btn.pack(side="right", padx=(8, 12), pady=12)
        self._update_button_style()

    def _update_button_style(self) -> None:
        colors = get_theme_colors(self._mode)
        if self._followed:
            self._btn.configure(
                text="Following",
                fg_color=colors["surface_elevated"],
                text_color=colors["text_primary"],
                hover_color=colors["card_hover"]
            )
        elif self._requested:
            self._btn.configure(
                text="Requested",
                fg_color=colors["surface_elevated"],
                text_color=colors["text_muted"],
                hover_color=colors["card_hover"]
            )
        else:
            self._btn.configure(
                text="Follow",
                fg_color=colors["primary"],
                text_color="#FFFFFF",
                hover_color=colors["primary_hover"]
            )

    def _toggle_follow(self) -> None:
        uid = self._user.get("id", 0)
        try:
            if self._followed or self._requested:
                res = self._api.unfollow_user(uid)
                self._followed = False
                self._requested = False
            else:
                res = self._api.follow_user(uid)
                self._followed = res.get("following", False)
                self._requested = res.get("requested", False)
            self._update_button_style()
        except Exception as e:
            logger.warning("Follow toggle error: %s", e)

    def _handle_click(self, uid: int) -> None:
        if self._on_click:
            self._on_click(uid)


class Toast(_FrameBase):
    """
    Ephemeral top-sliding banner displaying feedback toasts.
    Auto-dismisses after 3 seconds.
    """

    @classmethod
    def show(
        cls,
        root: Any,
        message: str,
        toast_type: str = "info",
        duration_ms: int = 3000
    ) -> Optional["Toast"]:
        if not _HAS_CTK or root is None:
            logger.info("Toast: [%s] %s", toast_type, message)
            return None

        toast = cls(root, message, toast_type)
        toast.place(relx=0.5, y=-30, anchor="center")
        toast.lift()
        slide_down_toast(toast)
        root.after(duration_ms, toast.dismiss)
        return toast

    def __init__(self, master: Any, message: str, toast_type: str = "info", **kwargs: Any) -> None:
        if _HAS_CTK:
            bg_color = "#262626"
            if toast_type == "error":
                bg_color = "#D92737"
            elif toast_type == "success":
                bg_color = "#28A745"

            super().__init__(
                master,
                fg_color=bg_color,
                corner_radius=18,
                border_width=1,
                border_color="#444444",
                **kwargs
            )
            lbl = ctk.CTkLabel(
                self,
                text=message,
                font=font_body(bold=True),
                text_color="#FFFFFF"
            )
            lbl.pack(padx=20, pady=8)

    def dismiss(self) -> None:
        if _HAS_CTK:
            def _destroy() -> None:
                try:
                    self.destroy()
                except Exception:
                    pass
            try:
                slide_up_dismiss(self, on_done=_destroy)
            except Exception:
                _destroy()


class ConfirmDialog(_ToplevelBase):
    """
    Modal confirmation prompt with Confirm and Cancel actions.
    """

    def __init__(
        self,
        parent: Any,
        title: str,
        message: str,
        confirm_text: str = "Confirm",
        cancel_text: str = "Cancel",
        on_confirm: Optional[Callable[[], None]] = None,
        is_danger: bool = True,
        mode: str = "dark"
    ) -> None:
        if _HAS_CTK and parent is not None:
            super().__init__(parent)
            self.title(title)
            self.geometry("340x180")
            self.resizable(False, False)
            self.transient(parent)
            self.after(100, self._safe_grab)
            fade_in_window(self)

            colors = get_theme_colors(mode)
            self.configure(fg_color=colors["surface"])

            # Center on parent
            try:
                x = parent.winfo_x() + (parent.winfo_width() - 340) // 2
                y = parent.winfo_y() + (parent.winfo_height() - 180) // 2
                self.geometry(f"+{x}+{y}")
            except Exception:
                pass

            # Title
            t_lbl = ctk.CTkLabel(self, text=title, font=font_h2(), text_color=colors["text_primary"])
            t_lbl.pack(pady=(16, 6))

            # Message
            m_lbl = ctk.CTkLabel(
                self,
                text=message,
                font=font_body(),
                text_color=colors["text_secondary"],
                wraplength=300
            )
            m_lbl.pack(pady=(0, 16))

            # Buttons Frame
            btn_frame = ctk.CTkFrame(self, fg_color="transparent")
            btn_frame.pack(fill="x", padx=20, pady=(0, 16))

            cancel_btn = ctk.CTkButton(
                btn_frame,
                text=cancel_text,
                font=font_body(),
                fg_color=colors["surface_elevated"],
                hover_color=colors["card_hover"],
                text_color=colors["text_primary"],
                width=130,
                height=36,
                corner_radius=RADIUS_BUTTON,
                command=self._cancel
            )
            cancel_btn.pack(side="left", padx=(0, 8), expand=True)

            confirm_fg = colors["danger"] if is_danger else colors["primary"]
            confirm_hover = colors["danger_hover"] if is_danger else colors["primary_hover"]

            confirm_btn = ctk.CTkButton(
                btn_frame,
                text=confirm_text,
                font=font_body(bold=True),
                fg_color=confirm_fg,
                hover_color=confirm_hover,
                text_color="#FFFFFF",
                width=130,
                height=36,
                corner_radius=RADIUS_BUTTON,
                command=lambda: self._confirm(on_confirm)
            )
            confirm_btn.pack(side="right", padx=(8, 0), expand=True)
        else:
            self._on_confirm = on_confirm

    def _safe_grab(self) -> None:
        try:
            if self.winfo_exists():
                self.grab_set()
        except Exception:
            pass

    def _cancel(self) -> None:
        if _HAS_CTK:
            try:
                self.grab_release()
            except Exception:
                pass
            self.destroy()

    def _confirm(self, callback: Optional[Callable[[], None]]) -> None:
        self._cancel()
        if callback:
            callback()
