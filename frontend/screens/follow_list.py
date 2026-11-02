"""
Follow List Modal Dialog for SocialApp.
Displays paginated followers or following list for a given user, with interactive
follow/unfollow action buttons and profile navigation.

API Calls:
- GET /api/users/{id}/followers?page=N&size=20 -> {items: UserSummary[], hasNext}
- GET /api/users/{id}/following?page=N&size=20 -> {items: UserSummary[], hasNext}
"""

import logging
from typing import Any, Callable, Dict, List, Optional

from ..async_utils import run_async
from ..theme import (
    get_theme_colors,
    font_body,
    font_caption,
    font_h2,
    RADIUS_BUTTON,
)
from ..widgets import UserRow, Toast

from ..theme import UI_FONT
from ..anim import fade_in_window, pop_button

logger = logging.getLogger("SocialApp.screens.follow_list")

_HAS_CTK = False
try:
    import customtkinter as ctk
    _HAS_CTK = True
except Exception:
    ctk = None
    _HAS_CTK = False

_ToplevelBase = ctk.CTkToplevel if _HAS_CTK else object


class FollowListModal(_ToplevelBase):
    """
    Modal window displaying followers or following accounts.
    """

    def __init__(
        self,
        parent: Any,
        user_id: int,
        list_type: str,  # "followers" or "following"
        api: Any,
        on_user_click: Optional[Callable[[int], None]] = None,
        mode: str = "dark",
        **kwargs: Any
    ) -> None:
        self.user_id = user_id
        self.list_type = list_type.lower()
        self.api = api
        self.on_user_click = on_user_click
        self.mode = mode

        self.users: List[Dict[str, Any]] = []
        self.current_page = 0
        self.has_next = False
        self.is_loading = False

        title = "Followers" if self.list_type == "followers" else "Following"

        if _HAS_CTK and parent is not None:
            super().__init__(parent)
            self.title(title)
            self.geometry("400x540")
            self.resizable(False, False)
            self.transient(parent)
            self.after(100, self._safe_grab)
            fade_in_window(self)

            colors = get_theme_colors(mode)
            self.configure(fg_color=colors["surface"])

            try:
                x = parent.winfo_x() + (parent.winfo_width() - 400) // 2
                y = parent.winfo_y() + (parent.winfo_height() - 540) // 2
                self.geometry(f"+{max(0, x)}+{max(0, y)}")
            except Exception:
                pass

            self._build_ui(title)
            self._load_data(page=0)
        else:
            self._parent = parent

    def _safe_grab(self) -> None:
        try:
            if self.winfo_exists():
                self.grab_set()
        except Exception:
            pass

    def _build_ui(self, title: str) -> None:
        if not _HAS_CTK:
            return

        colors = get_theme_colors(self.mode)

        # Header Frame
        header = ctk.CTkFrame(self, height=48, fg_color=colors["surface"], corner_radius=0)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        title_lbl = ctk.CTkLabel(
            header,
            text=title,
            font=font_h2(),
            text_color=colors["text_primary"]
        )
        title_lbl.pack(side="left", padx=16, pady=10)

        close_btn = ctk.CTkButton(
            header,
            text="✕",
            width=32,
            height=32,
            font=(UI_FONT, 16),
            fg_color="transparent",
            text_color=colors["text_muted"],
            hover_color=colors["surface_elevated"],
            command=self._close
        )
        close_btn.pack(side="right", padx=12, pady=8)

        # Divider
        div = ctk.CTkFrame(self, height=1, fg_color=colors["divider"])
        div.pack(fill="x")

        # Scrollable list
        self._scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll_frame.pack(fill="both", expand=True, padx=4, pady=4)

    def _close(self) -> None:
        if _HAS_CTK:
            try:
                self.grab_release()
                self.destroy()
            except Exception:
                pass

    def _load_data(self, page: int = 0) -> None:
        if self.is_loading:
            return
        self.is_loading = True

        def worker() -> Dict[str, Any]:
            if self.list_type == "followers":
                return self.api.get_followers(self.user_id, page=page, size=20)
            else:
                return self.api.get_following(self.user_id, page=page, size=20)

        def on_success(res: Dict[str, Any]) -> None:
            self.is_loading = False
            items = res.get("items", [])
            self.has_next = res.get("hasNext", False)
            self.current_page = page

            if page == 0:
                self.users = items
                self._render_users(clear=True)
            else:
                self.users.extend(items)
                self._render_users(clear=False, new_items=items)

        def on_error(exc: Exception) -> None:
            self.is_loading = False
            logger.warning("Failed to load %s: %s", self.list_type, exc)
            if _HAS_CTK:
                Toast.show(self, f"Failed to load: {exc}", toast_type="error")

        run_async(worker, on_success=on_success, on_error=on_error)

    def _render_users(self, clear: bool = True, new_items: Optional[List[Dict[str, Any]]] = None) -> None:
        if not _HAS_CTK or not hasattr(self, "_scroll_frame"):
            return

        if clear:
            for child in self._scroll_frame.winfo_children():
                child.destroy()

        target_list = new_items if new_items is not None else self.users

        if not self.users:
            empty_lbl = ctk.CTkLabel(
                self._scroll_frame,
                text=f"No {self.list_type} yet.",
                font=font_body(),
                text_color=get_theme_colors(self.mode)["text_muted"]
            )
            empty_lbl.pack(pady=40)
            return

        for user in target_list:
            row = UserRow(
                self._scroll_frame,
                user_summary=user,
                api=self.api,
                on_click=self._handle_user_selected,
                mode=self.mode
            )
            row.pack(fill="x", padx=4, pady=2)

        if self.has_next:
            more_btn = ctk.CTkButton(
                self._scroll_frame,
                text="Load more",
                font=font_caption(bold=True),
                height=30,
                fg_color="transparent",
                text_color=get_theme_colors(self.mode)["primary"],
                hover_color=get_theme_colors(self.mode)["surface_elevated"],
                command=lambda: self._load_data(page=self.current_page + 1)
            )
            more_btn.pack(pady=8)

    def _handle_user_selected(self, uid: int) -> None:
        self._close()
        if self.on_user_click:
            self.on_user_click(uid)
