"""
Direct Messages Screen for SocialApp.
Provides inbox conversation overview, conversation selection, interactive chat thread
with sent/received message bubbles, real-time message sending, and timestamp formatting.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Callable, Dict, List, Optional

from ..theme import (
    get_theme_colors,
    font_body,
    font_caption,
    font_h2,
    font_small,
    RADIUS_BUTTON,
    RADIUS_ENTRY,
    style_entry,
    style_primary_button,
)
from ..widgets import AvatarView

from ..theme import UI_FONT

logger = logging.getLogger("SocialApp.screens.messages")

_HAS_CTK = False
try:
    import customtkinter as ctk
    _HAS_CTK = True
except Exception:
    ctk = None
    _HAS_CTK = False

_FrameBase = ctk.CTkFrame if _HAS_CTK else object


class MessagesScreen(_FrameBase):
    """
    Direct Messaging UI managing inbox threads, message history, and outgoing message bubbles.
    """

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

        # Seeded demo conversations
        self.conversations: List[Dict[str, Any]] = [
            {
                "id": 1,
                "user": {
                    "id": 1,
                    "username": "alex_adventures",
                    "avatarUrl": "",
                },
                "last_message": "Hey! Did you check out the new mountain trail video?",
                "time": "10m",
                "unread": True,
                "messages": [
                    {"id": 101, "sender_id": 1, "text": "Hey there! How's your week going?", "time": "2h ago"},
                    {"id": 102, "sender_id": 0, "text": "Pretty good! Just editing some new photos.", "time": "1h ago"},
                    {"id": 103, "sender_id": 1, "text": "Hey! Did you check out the new mountain trail video?", "time": "10m ago"},
                ]
            },
            {
                "id": 2,
                "user": {
                    "id": 2,
                    "username": "sarah_codes",
                    "avatarUrl": "",
                },
                "last_message": "Awesome implementation on the async queue pump!",
                "time": "1h",
                "unread": False,
                "messages": [
                    {"id": 201, "sender_id": 2, "text": "Loved your latest tech post on desktop clients.", "time": "3h ago"},
                    {"id": 202, "sender_id": 0, "text": "Thanks Sarah! Built it using CustomTkinter & VLC.", "time": "2h ago"},
                    {"id": 203, "sender_id": 2, "text": "Awesome implementation on the async queue pump!", "time": "1h ago"},
                ]
            },
            {
                "id": 3,
                "user": {
                    "id": 3,
                    "username": "marco_foodie",
                    "avatarUrl": "",
                },
                "last_message": "Sending you that homemade sourdough recipe tonight 🥖",
                "time": "1d",
                "unread": False,
                "messages": [
                    {"id": 301, "sender_id": 3, "text": "Sending you that homemade sourdough recipe tonight 🥖", "time": "1d ago"}
                ]
            }
        ]

        self.active_conv: Optional[Dict[str, Any]] = None

        if _HAS_CTK:
            super().__init__(master, fg_color="transparent", **kwargs)
            self._build_ui()
            self._show_inbox()
        else:
            self._frame = None

    def _build_ui(self) -> None:
        if not _HAS_CTK:
            return

        colors = get_theme_colors(self.mode)

        # 1. Inbox Container (list of threads)
        self._inbox_view = ctk.CTkFrame(self, fg_color="transparent")

        inbox_header = ctk.CTkFrame(self._inbox_view, height=50, fg_color="transparent")
        inbox_header.pack(fill="x", padx=16, pady=(10, 4))

        inbox_title = ctk.CTkLabel(
            inbox_header,
            text="Direct Messages",
            font=font_h2(),
            text_color=colors["text_primary"]
        )
        inbox_title.pack(side="left")

        self._inbox_scroll = ctk.CTkScrollableFrame(self._inbox_view, fg_color="transparent")
        self._inbox_scroll.pack(fill="both", expand=True, padx=4, pady=4)

        # 2. Chat Thread View Container
        self._thread_view = ctk.CTkFrame(self, fg_color="transparent")

        # Thread Header: Back button, Avatar, Username
        self._thread_header = ctk.CTkFrame(self._thread_view, height=52, fg_color=colors["surface"], corner_radius=0)
        self._thread_header.pack(fill="x", side="top")
        self._thread_header.pack_propagate(False)

        back_btn = ctk.CTkButton(
            self._thread_header,
            text="←",
            width=32,
            height=32,
            font=(UI_FONT, 16, "bold"),
            fg_color="transparent",
            text_color=colors["text_primary"],
            hover_color=colors["surface_elevated"],
            command=self._show_inbox
        )
        back_btn.pack(side="left", padx=(10, 4))

        self._thread_avatar = AvatarView(self._thread_header, size=32)
        self._thread_avatar.pack(side="left", padx=4)

        self._thread_username_lbl = ctk.CTkLabel(
            self._thread_header,
            text="",
            font=font_body(bold=True),
            text_color=colors["text_primary"]
        )
        self._thread_username_lbl.pack(side="left", padx=8)

        # Bottom Input Bar
        self._input_bar = ctk.CTkFrame(self._thread_view, height=56, fg_color=colors["surface"], corner_radius=0)
        self._input_bar.pack(fill="x", side="bottom")
        self._input_bar.pack_propagate(False)

        input_box = ctk.CTkFrame(self._input_bar, fg_color="transparent")
        input_box.pack(fill="both", expand=True, padx=12, pady=8)

        self._message_entry = ctk.CTkEntry(
            input_box,
            placeholder_text="Message…",
            height=36,
            corner_radius=RADIUS_ENTRY,
            font=font_body()
        )
        style_entry(self._message_entry, self.mode)
        self._message_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._message_entry.bind("<Return>", lambda e: self._send_message())

        self._send_btn = ctk.CTkButton(
            input_box,
            text="Send",
            width=60,
            height=36,
            font=font_body(bold=True),
            corner_radius=RADIUS_BUTTON,
            command=self._send_message
        )
        style_primary_button(self._send_btn, self.mode)
        self._send_btn.pack(side="right")

        # Messages Scroll Area
        self._messages_scroll = ctk.CTkScrollableFrame(self._thread_view, fg_color="transparent")
        self._messages_scroll.pack(fill="both", expand=True, padx=8, pady=4)

    def _show_inbox(self) -> None:
        if not _HAS_CTK:
            return
        self._thread_view.pack_forget()
        self._inbox_view.pack(fill="both", expand=True)
        self._render_inbox()

    def _render_inbox(self) -> None:
        if not _HAS_CTK or not hasattr(self, "_inbox_scroll"):
            return

        for child in self._inbox_scroll.winfo_children():
            child.destroy()

        colors = get_theme_colors(self.mode)

        for conv in self.conversations:
            user = conv.get("user", {})
            uid = user.get("id", 0)
            username = user.get("username", "user")
            last_msg = conv.get("last_message", "")
            t_str = conv.get("time", "")
            unread = conv.get("unread", False)

            row = ctk.CTkFrame(
                self._inbox_scroll,
                height=64,
                fg_color=colors["surface_elevated"] if unread else "transparent",
                corner_radius=8
            )
            row.pack(fill="x", padx=4, pady=3)
            row.pack_propagate(False)

            av = AvatarView(row, image_url_or_path=user.get("avatarUrl", ""), size=44)
            av.pack(side="left", padx=(10, 10))

            info = ctk.CTkFrame(row, fg_color="transparent")
            info.pack(side="left", fill="both", expand=True, pady=10)

            title_row = ctk.CTkFrame(info, fg_color="transparent")
            title_row.pack(fill="x")

            name_lbl = ctk.CTkLabel(
                title_row,
                text=username,
                font=font_body(bold=True),
                text_color=colors["text_primary"],
                anchor="w"
            )
            name_lbl.pack(side="left")

            time_lbl = ctk.CTkLabel(
                title_row,
                text=f" • {t_str}",
                font=font_caption(),
                text_color=colors["text_muted"],
                anchor="w"
            )
            time_lbl.pack(side="left")

            msg_lbl = ctk.CTkLabel(
                info,
                text=last_msg,
                font=font_caption(bold=unread),
                text_color=colors["text_primary"] if unread else colors["text_secondary"],
                anchor="w"
            )
            msg_lbl.pack(fill="x", anchor="w")

            # Click row opens thread
            for widget in (row, info, title_row, name_lbl, time_lbl, msg_lbl):
                widget.bind("<Button-1>", lambda e, c=conv: self._open_thread(c))

    def _open_thread(self, conv: Dict[str, Any]) -> None:
        self.active_conv = conv
        conv["unread"] = False

        if not _HAS_CTK:
            return

        self._inbox_view.pack_forget()
        self._thread_view.pack(fill="both", expand=True)

        user = conv.get("user", {})
        self._thread_username_lbl.configure(text=user.get("username", "user"))
        self._thread_avatar.set_image(user.get("avatarUrl", ""))

        self._render_messages()

    def _render_messages(self) -> None:
        if not _HAS_CTK or not hasattr(self, "_messages_scroll") or not self.active_conv:
            return

        for child in self._messages_scroll.winfo_children():
            child.destroy()

        colors = get_theme_colors(self.mode)
        msgs = self.active_conv.get("messages", [])

        for msg in msgs:
            is_me = (msg.get("sender_id") == 0)
            text = msg.get("text", "")
            time_str = msg.get("time", "")

            bubble_row = ctk.CTkFrame(self._messages_scroll, fg_color="transparent")
            bubble_row.pack(fill="x", padx=6, pady=4)

            bubble = ctk.CTkFrame(
                bubble_row,
                fg_color=colors["primary"] if is_me else colors["surface_elevated"],
                corner_radius=14
            )
            if is_me:
                bubble.pack(side="right", padx=(40, 4))
            else:
                bubble.pack(side="left", padx=(4, 40))

            t_lbl = ctk.CTkLabel(
                bubble,
                text=text,
                font=font_body(),
                text_color="#FFFFFF" if is_me else colors["text_primary"],
                wraplength=260,
                justify="left"
            )
            t_lbl.pack(padx=12, pady=8)

    def _send_message(self, text_override: Optional[str] = None) -> None:
        if not self.active_conv:
            return

        text = text_override
        if text is None and _HAS_CTK and hasattr(self, "_message_entry"):
            text = self._message_entry.get().strip()
            self._message_entry.delete(0, "end")

        if not text:
            return

        new_msg = {
            "id": len(self.active_conv.get("messages", [])) + 1,
            "sender_id": 0,  # 0 indicates current user
            "text": text,
            "time": "Just now"
        }
        self.active_conv["messages"].append(new_msg)
        self.active_conv["last_message"] = text
        self.active_conv["time"] = "Just now"

        self._render_messages()

    def on_enter(self, **kwargs: Any) -> None:
        if not self.active_conv:
            self._show_inbox()

    def on_leave(self) -> None:
        pass
