"""
Activity and Notifications Screen for SocialApp.
Renders inbound follow requests with Accept and Decline actions, and interaction notifications
(likes, comments, mentions) with relative timestamps.

API Calls:
- GET /api/follow-requests?page=N&size=20 -> {items: UserSummary[], hasNext}
- POST /api/follow-requests/{userId}/accept -> 204
- POST /api/follow-requests/{userId}/decline -> 204
"""

import logging
from typing import Any, Callable, Dict, List, Optional

from ..async_utils import run_async
from ..theme import (
    get_theme_colors,
    font_body,
    font_caption,
    font_h2,
    font_small,
    RADIUS_BUTTON,
    style_primary_button,
    style_secondary_button,
)
from ..widgets import AvatarView, Toast

logger = logging.getLogger("SocialApp.screens.activity")

_HAS_CTK = False
try:
    import customtkinter as ctk
    _HAS_CTK = True
except Exception:
    ctk = None
    _HAS_CTK = False

_FrameBase = ctk.CTkFrame if _HAS_CTK else object


class ActivityScreen(_FrameBase):
    """
    Activity and notifications view managing pending follow requests and interaction alerts.
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

        self.follow_requests: List[Dict[str, Any]] = []
        self.notifications: List[Dict[str, Any]] = [
            {
                "id": 1,
                "user": {"id": 1, "username": "alex_adventures", "avatarUrl": ""},
                "text": "liked your photo.",
                "time": "15m",
            },
            {
                "id": 2,
                "user": {"id": 2, "username": "sarah_codes", "avatarUrl": ""},
                "text": "commented: 'Great shot!'",
                "time": "1h",
            },
            {
                "id": 3,
                "user": {"id": 3, "username": "marco_foodie", "avatarUrl": ""},
                "text": "started following you.",
                "time": "3h",
            },
            {
                "id": 4,
                "user": {"id": 4, "username": "elena_fit", "avatarUrl": ""},
                "text": "liked your reel.",
                "time": "1d",
            }
        ]
        self.is_loading = False

        if _HAS_CTK:
            super().__init__(master, fg_color="transparent", **kwargs)
            self._build_ui()
        else:
            self._frame = None

    def _build_ui(self) -> None:
        if not _HAS_CTK:
            return

        colors = get_theme_colors(self.mode)

        # Header Title
        title_lbl = ctk.CTkLabel(
            self,
            text="Notifications",
            font=font_h2(),
            text_color=colors["text_primary"]
        )
        title_lbl.pack(pady=(12, 6))

        # Scrollable Viewport
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True, padx=4, pady=0)

        # 1. Follow Requests Section
        self._requests_container = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._requests_container.pack(fill="x", padx=8, pady=(4, 10))

        # 2. Activity / Interactions Section
        self._activity_container = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._activity_container.pack(fill="x", padx=8, pady=(4, 10))

    def load_data(self) -> None:
        api = self.app_state.api if self.app_state else None
        if not api or self.is_loading:
            return
        self.is_loading = True

        def worker() -> Dict[str, Any]:
            return api.get_follow_requests(page=0, size=20)

        def on_success(res: Dict[str, Any]) -> None:
            self.is_loading = False
            self.follow_requests = res.get("items", [])
            self._render_follow_requests()
            self._render_activity()

        def on_error(exc: Exception) -> None:
            self.is_loading = False
            logger.warning("Failed to fetch follow requests: %s", exc)
            self._render_activity()

        run_async(worker, on_success=on_success, on_error=on_error)

    def _render_follow_requests(self) -> None:
        if not _HAS_CTK or not hasattr(self, "_requests_container"):
            return

        for child in self._requests_container.winfo_children():
            child.destroy()

        colors = get_theme_colors(self.mode)

        if not self.follow_requests:
            self._requests_container.pack_forget()
            return

        self._requests_container.pack(fill="x", padx=8, pady=(4, 10))

        sec_title = ctk.CTkLabel(
            self._requests_container,
            text=f"Follow Requests ({len(self.follow_requests)})",
            font=font_caption(bold=True),
            text_color=colors["text_secondary"],
            anchor="w"
        )
        sec_title.pack(fill="x", pady=(0, 6))

        for req in self.follow_requests:
            uid = req.get("id", 0)
            username = req.get("username", "user")
            avatar_url = req.get("avatarUrl", "")

            row = ctk.CTkFrame(self._requests_container, fg_color="transparent", height=50)
            row.pack(fill="x", pady=4)

            av = AvatarView(row, image_url_or_path=avatar_url, size=40, command=lambda u=uid: self._handle_user_clicked(u))
            av.pack(side="left", padx=(0, 8))

            name_lbl = ctk.CTkLabel(
                row,
                text=f"{username}\nwants to follow you",
                font=font_caption(bold=True),
                text_color=colors["text_primary"],
                anchor="w",
                justify="left"
            )
            name_lbl.pack(side="left", fill="both", expand=True)

            # Accept Button
            acc_btn = ctk.CTkButton(
                row,
                text="Confirm",
                font=font_small(),
                width=64,
                height=28,
                corner_radius=RADIUS_BUTTON,
                fg_color=colors["primary"],
                hover_color=colors["primary_hover"],
                text_color="#FFFFFF",
                command=lambda u=uid, r=row: self._accept_request(u, r)
            )
            acc_btn.pack(side="right", padx=(4, 0))

            # Decline Button
            dec_btn = ctk.CTkButton(
                row,
                text="Delete",
                font=font_small(),
                width=60,
                height=28,
                corner_radius=RADIUS_BUTTON,
                fg_color=colors["surface_elevated"],
                hover_color=colors["card_hover"],
                text_color=colors["text_primary"],
                command=lambda u=uid, r=row: self._decline_request(u, r)
            )
            dec_btn.pack(side="right", padx=(0, 4))

        # Divider
        div = ctk.CTkFrame(self._requests_container, height=1, fg_color=colors["divider"])
        div.pack(fill="x", pady=(10, 4))

    def _render_activity(self) -> None:
        if not _HAS_CTK or not hasattr(self, "_activity_container"):
            return

        for child in self._activity_container.winfo_children():
            child.destroy()

        colors = get_theme_colors(self.mode)

        sec_title = ctk.CTkLabel(
            self._activity_container,
            text="Recent Activity",
            font=font_caption(bold=True),
            text_color=colors["text_secondary"],
            anchor="w"
        )
        sec_title.pack(fill="x", pady=(4, 6))

        for act in self.notifications:
            user = act.get("user", {})
            uid = user.get("id", 0)
            username = user.get("username", "user")
            text = act.get("text", "")
            time_str = act.get("time", "")

            row = ctk.CTkFrame(self._activity_container, fg_color="transparent", height=46)
            row.pack(fill="x", pady=4)

            av = AvatarView(row, image_url_or_path=user.get("avatarUrl", ""), size=38, command=lambda u=uid: self._handle_user_clicked(u))
            av.pack(side="left", padx=(0, 8))

            text_frame = ctk.CTkFrame(row, fg_color="transparent")
            text_frame.pack(side="left", fill="both", expand=True)

            msg_lbl = ctk.CTkLabel(
                text_frame,
                text=f"{username} {text}",
                font=font_body(),
                text_color=colors["text_primary"],
                anchor="w",
                justify="left",
                wraplength=280
            )
            msg_lbl.pack(fill="x", anchor="w")

            time_lbl = ctk.CTkLabel(
                text_frame,
                text=time_str,
                font=font_small(),
                text_color=colors["text_muted"],
                anchor="w"
            )
            time_lbl.pack(fill="x", anchor="w")

    def _accept_request(self, user_id: int, row_widget: Any) -> None:
        api = self.app_state.api if self.app_state else None
        if not api:
            return

        def worker() -> None:
            api.accept_follow_request(user_id)

        def on_success(_: Any) -> None:
            if _HAS_CTK:
                row_widget.destroy()
                Toast.show(self.winfo_toplevel(), "Follow request accepted.", toast_type="success")
            self.follow_requests = [r for r in self.follow_requests if r.get("id") != user_id]
            if not self.follow_requests and hasattr(self, "_requests_container"):
                self._requests_container.pack_forget()

        run_async(worker, on_success=on_success)

    def _decline_request(self, user_id: int, row_widget: Any) -> None:
        api = self.app_state.api if self.app_state else None
        if not api:
            return

        def worker() -> None:
            api.decline_follow_request(user_id)

        def on_success(_: Any) -> None:
            if _HAS_CTK:
                row_widget.destroy()
            self.follow_requests = [r for r in self.follow_requests if r.get("id") != user_id]
            if not self.follow_requests and hasattr(self, "_requests_container"):
                self._requests_container.pack_forget()

        run_async(worker, on_success=on_success)

    def _handle_user_clicked(self, uid: int) -> None:
        if self.on_user_click:
            self.on_user_click(uid)
        elif self.app_state and self.app_state.router:
            from .profile import ProfileScreen
            self.app_state.router.push(ProfileScreen, title="Profile", app_state=self.app_state, user_id=uid, mode=self.mode)

    def on_enter(self, **kwargs: Any) -> None:
        self.load_data()

    def on_leave(self) -> None:
        pass
