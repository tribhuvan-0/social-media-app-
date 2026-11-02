"""
Explore Screen for SocialApp.
Provides search filtering across tags and accounts, suggested users showcase,
and an interactive 3-column media discovery grid with thumbnail caching and video badges.

API Calls:
- GET /api/users/suggested -> {items: UserSummary[]}
- GET /api/reels?size=18 -> {items: MediaCard[], hasNext}
- GET /api/media/{id} -> MediaCard
"""

import logging
from typing import Any, Callable, Dict, List, Optional

from ..async_utils import run_async
from ..cache import load_image_async
from ..theme import (
    get_theme_colors,
    font_body,
    font_caption,
    font_h2,
    RADIUS_BUTTON,
    RADIUS_ENTRY,
    style_entry,
)
from ..widgets import AvatarView, UserRow, Toast

from ..theme import UI_FONT

logger = logging.getLogger("SocialApp.screens.explore")

_HAS_CTK = False
try:
    import customtkinter as ctk
    _HAS_CTK = True
except Exception:
    ctk = None
    _HAS_CTK = False

_FrameBase = ctk.CTkFrame if _HAS_CTK else object


class ExploreScreen(_FrameBase):
    """
    Explore discovery hub featuring search bar, suggested accounts row, and 3-column media grid.
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

        self.all_media: List[Dict[str, Any]] = []
        self.suggested_users: List[Dict[str, Any]] = []
        self.filtered_media: List[Dict[str, Any]] = []
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

        # Search Bar Header
        search_frame = ctk.CTkFrame(self, height=52, fg_color="transparent")
        search_frame.pack(fill="x", padx=12, pady=(8, 4))

        self._search_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="🔍 Search accounts, tags #photography...",
            height=38,
            corner_radius=RADIUS_ENTRY,
            font=font_body()
        )
        style_entry(self._search_entry, self.mode)
        self._search_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._search_entry.bind("<KeyRelease>", lambda e: self._on_search_query_changed())

        self._clear_btn = ctk.CTkButton(
            search_frame,
            text="Clear",
            width=58,
            height=38,
            font=font_caption(bold=True),
            corner_radius=RADIUS_BUTTON,
            fg_color=colors["surface_elevated"],
            text_color=colors["text_primary"],
            hover_color=colors["card_hover"],
            command=self._clear_search
        )
        self._clear_btn.pack(side="right")

        # Scrollable Viewport
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True, padx=4, pady=0)

        # 1. Suggested Users Horizontal Section
        self._suggested_section = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._suggested_section.pack(fill="x", padx=8, pady=(4, 12))

        sug_title = ctk.CTkLabel(
            self._suggested_section,
            text="Discover Creators",
            font=font_caption(bold=True),
            text_color=colors["text_secondary"],
            anchor="w"
        )
        sug_title.pack(fill="x", pady=(0, 6))

        self._sug_scroll = ctk.CTkScrollableFrame(
            self._suggested_section,
            orientation="horizontal",
            height=70,
            fg_color="transparent"
        )
        self._sug_scroll.pack(fill="x")

        # Divider
        div = ctk.CTkFrame(self._scroll, height=1, fg_color=colors["divider"])
        div.pack(fill="x", padx=8, pady=(0, 10))

        # 2. 3-Column Media Discovery Grid
        self._grid_frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._grid_frame.pack(fill="both", expand=True, padx=4)

    def _clear_search(self) -> None:
        if not _HAS_CTK or not hasattr(self, "_search_entry"):
            return
        self._search_entry.delete(0, "end")
        self._on_search_query_changed()

    def _on_search_query_changed(self) -> None:
        if not _HAS_CTK or not hasattr(self, "_search_entry"):
            return

        query = self._search_entry.get().strip().lower()
        if not query:
            self.filtered_media = list(self.all_media)
        else:
            cleaned_query = query.lstrip("#")
            self.filtered_media = [
                m for m in self.all_media
                if cleaned_query in m.get("caption", "").lower()
                or any(cleaned_query in tag.lower() for tag in m.get("tags", []))
                or cleaned_query in m.get("user", {}).get("username", "").lower()
            ]

        self._render_grid()

    def load_content(self) -> None:
        api = self.app_state.api if self.app_state else None
        if not api or self.is_loading:
            return
        self.is_loading = True

        def worker() -> Dict[str, Any]:
            reels_res = api.get_reels(size=18)
            sug_res = api.get_suggested_users()
            return {
                "media": reels_res.get("items", []),
                "suggested": sug_res.get("items", [])
            }

        def on_success(res: Dict[str, Any]) -> None:
            self.is_loading = False
            self.all_media = res.get("media", [])
            self.filtered_media = list(self.all_media)
            self.suggested_users = res.get("suggested", [])
            self._render_suggested()
            self._render_grid()

        def on_error(exc: Exception) -> None:
            self.is_loading = False
            logger.warning("Failed to load explore content: %s", exc)

        run_async(worker, on_success=on_success, on_error=on_error)

    def _render_suggested(self) -> None:
        if not _HAS_CTK or not hasattr(self, "_sug_scroll"):
            return

        for child in self._sug_scroll.winfo_children():
            child.destroy()

        colors = get_theme_colors(self.mode)
        api = self.app_state.api if self.app_state else None

        for user in self.suggested_users:
            uid = user.get("id", 0)
            username = user.get("username", "user")
            avatar_url = user.get("avatarUrl", "")

            user_badge = ctk.CTkFrame(
                self._sug_scroll,
                fg_color=colors["surface_elevated"],
                corner_radius=12,
                border_width=1,
                border_color=colors["border"]
            )
            user_badge.pack(side="left", padx=4, pady=2)

            av = AvatarView(
                user_badge,
                image_url_or_path=avatar_url,
                size=36,
                command=lambda u=uid: self._handle_user_clicked(u)
            )
            av.pack(side="left", padx=(6, 4), pady=4)

            name_lbl = ctk.CTkLabel(
                user_badge,
                text=username[:10],
                font=font_caption(bold=True),
                text_color=colors["text_primary"],
                cursor="hand2"
            )
            name_lbl.pack(side="left", padx=(0, 8), pady=4)
            name_lbl.bind("<Button-1>", lambda e, u=uid: self._handle_user_clicked(u))

    def _render_grid(self) -> None:
        if not _HAS_CTK or not hasattr(self, "_grid_frame"):
            return

        for child in self._grid_frame.winfo_children():
            child.destroy()

        colors = get_theme_colors(self.mode)

        if not self.filtered_media:
            empty_lbl = ctk.CTkLabel(
                self._grid_frame,
                text="No media found matching your search.",
                font=font_body(),
                text_color=colors["text_muted"]
            )
            empty_lbl.pack(pady=40)
            return

        # 3 columns layout
        col_width = 146
        col_height = 146

        for i, item in enumerate(self.filtered_media):
            row = i // 3
            col = i % 3

            cell = ctk.CTkFrame(
                self._grid_frame,
                width=col_width,
                height=col_height,
                corner_radius=4,
                fg_color=colors["surface"]
            )
            cell.grid(row=row, column=col, padx=2, pady=2)
            cell.pack_propagate(False)

            thumb_label = ctk.CTkLabel(cell, text="")
            thumb_label.place(relx=0, rely=0, relwidth=1.0, relheight=1.0)

            thumb_url = item.get("thumbnailUrl") or item.get("mediaUrl", "")

            def on_ready(wrapped: Any, lbl=thumb_label) -> None:
                try:
                    lbl.configure(image=wrapped)
                except Exception:
                    pass

            placeholder = load_image_async(
                thumb_url,
                (col_width, col_height),
                corner_radius=4,
                on_ready=on_ready
            )
            thumb_label.configure(image=placeholder)

            # Video indicator badge
            if item.get("mediaKind") == "VIDEO" or item.get("type") == "REEL":
                badge = ctk.CTkLabel(
                    cell,
                    text="🎬",
                    font=(UI_FONT, 12),
                    fg_color="#1A1A1A",
                    corner_radius=4,
                    width=22,
                    height=22
                )
                badge.place(relx=0.88, rely=0.12, anchor="center")

            # Click tile opens media detail / post card
            mid = item.get("id", 0)
            thumb_label.bind("<Button-1>", lambda e, m_item=item: self._open_detail_modal(m_item))

    def _safe_grab_dlg(self, dlg: Any) -> None:
        try:
            if dlg.winfo_exists():
                dlg.grab_set()
        except Exception:
            pass

    def _open_detail_modal(self, item: Dict[str, Any]) -> None:
        if not _HAS_CTK:
            return

        # TopLevel modal viewing post/reel
        parent = self.winfo_toplevel()
        dlg = ctk.CTkToplevel(parent)
        dlg.title(f"Post by @{item.get('user', {}).get('username', 'user')}")
        dlg.geometry("460x700")
        dlg.resizable(False, False)
        dlg.transient(parent)
        dlg.after(100, lambda: self._safe_grab_dlg(dlg))

        colors = get_theme_colors(self.mode)
        dlg.configure(fg_color=colors["bg"])

        from ..widgets import PostCard
        card = PostCard(
            dlg,
            media_data=item,
            api=self.app_state.api if self.app_state else None,
            player=self.app_state.player if self.app_state else None,
            on_user_click=lambda u: [dlg.destroy(), self._handle_user_clicked(u)],
            mode=self.mode
        )
        card.pack(fill="both", expand=True, padx=8, pady=8)

        close_btn = ctk.CTkButton(
            dlg,
            text="Close",
            font=font_caption(bold=True),
            height=32,
            fg_color=colors["surface_elevated"],
            text_color=colors["text_primary"],
            hover_color=colors["card_hover"],
            command=dlg.destroy
        )
        close_btn.pack(pady=(0, 10))

    def _handle_user_clicked(self, user_id: int) -> None:
        if self.on_user_click:
            self.on_user_click(user_id)
        elif self.app_state and self.app_state.router:
            from .profile import ProfileScreen
            self.app_state.router.push(
                ProfileScreen,
                title="Profile",
                app_state=self.app_state,
                user_id=user_id,
                mode=self.mode
            )

    def on_enter(self, **kwargs: Any) -> None:
        if not self.all_media:
            self.load_content()

    def on_leave(self) -> None:
        pass
