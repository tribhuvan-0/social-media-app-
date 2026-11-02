"""
Home Feed Screen for SocialApp.
Displays horizontal Stories tray with StoryRing items, vertical scrollable feed of PostCards
with optimistic likes, inline video playback with view telemetry, comments modal opener,
share links, suggested users for empty feeds, and infinite scroll pagination.

API Calls:
- GET /api/stories -> {items: StoryGroup[]}
- GET /api/feed?page=N&size=10 -> {items: MediaCard[], hasNext}
- GET /api/users/suggested -> {items: UserSummary[]}
- POST /api/media/{id}/like, DELETE /api/media/{id}/like
- POST /api/media/{id}/share -> {shareCount, shareUrl}
- POST /api/media/{id}/view {watchMs, durationMs, completed} -> 204
- DELETE /api/media/{id} -> 204
- POST /api/users/{id}/follow, DELETE /api/users/{id}/follow
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Set

from ..async_utils import run_async
from ..theme import (
    get_theme_colors,
    font_body,
    font_caption,
    font_h2,
    RADIUS_BUTTON,
    style_primary_button,
)
from ..widgets import PostCard, StoryRing, UserRow, Toast
from .comments import CommentsModal
from .stories import StoriesViewerModal

logger = logging.getLogger("SocialApp.screens.home")

_HAS_CTK = False
try:
    import customtkinter as ctk
    _HAS_CTK = True
except Exception:
    ctk = None
    _HAS_CTK = False

_FrameBase = ctk.CTkFrame if _HAS_CTK else object


class HomeScreen(_FrameBase):
    """
    Primary Home Feed screen featuring Stories tray, PostCard stream, and Suggested Users empty state.
    """

    def __init__(
        self,
        master: Any,
        app_state: Any = None,
        on_user_click: Optional[Callable[[int], None]] = None,
        on_open_create_story: Optional[Callable[[], None]] = None,
        mode: str = "dark",
        **kwargs: Any
    ) -> None:
        self.app_state = app_state
        self.on_user_click = on_user_click
        self.on_open_create_story = on_open_create_story
        self.mode = mode

        self.story_groups: List[Dict[str, Any]] = []
        self.posts: List[Dict[str, Any]] = []
        self.suggested_users: List[Dict[str, Any]] = []
        self.current_page = 0
        self.has_next_page = False
        self.is_loading_feed = False
        self.is_loading_stories = False
        self._active_playing_card: Optional[Any] = None

        if _HAS_CTK:
            super().__init__(master, fg_color="transparent", **kwargs)
            self._build_ui()
        else:
            self._frame = None

    def _build_ui(self) -> None:
        if not _HAS_CTK:
            return

        colors = get_theme_colors(self.mode)

        # Top Control Bar (Refresh button & indicator)
        self._control_bar = ctk.CTkFrame(self, height=36, fg_color="transparent")
        self._control_bar.pack(fill="x", padx=12, pady=(4, 0))

        self._refresh_btn = ctk.CTkButton(
            self._control_bar,
            text="⟳ Refresh Feed",
            font=font_caption(bold=True),
            width=110,
            height=28,
            corner_radius=RADIUS_BUTTON,
            fg_color=colors["surface_elevated"],
            text_color=colors["text_primary"],
            hover_color=colors["card_hover"],
            command=self.refresh_all
        )
        self._refresh_btn.pack(side="left")

        # Scrollable Feed Container
        self._feed_scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._feed_scroll.pack(fill="both", expand=True, padx=0, pady=0)

        # 1. Stories Tray
        self._stories_container = ctk.CTkFrame(
            self._feed_scroll,
            height=96,
            fg_color="transparent"
        )
        self._stories_container.pack(fill="x", padx=4, pady=(2, 6))

        # Horizontal Scroll Frame for Stories
        self._stories_scroll = ctk.CTkScrollableFrame(
            self._stories_container,
            orientation="horizontal",
            height=88,
            fg_color="transparent"
        )
        self._stories_scroll.pack(fill="x", expand=True)

        # Stories Tray Bottom Divider
        div = ctk.CTkFrame(self._feed_scroll, height=1, fg_color=colors["divider"])
        div.pack(fill="x", pady=(0, 6))

        # 2. Posts Stream Container
        self._posts_container = ctk.CTkFrame(self._feed_scroll, fg_color="transparent")
        self._posts_container.pack(fill="x", expand=True)

        # 3. Empty State & Suggested Users Container
        self._empty_container = ctk.CTkFrame(self._feed_scroll, fg_color="transparent")

        # 4. Footer Load More
        self._footer_frame = ctk.CTkFrame(self._feed_scroll, height=50, fg_color="transparent")
        self._footer_frame.pack(fill="x", pady=8)

        self._load_more_btn = ctk.CTkButton(
            self._footer_frame,
            text="Load more posts",
            font=font_caption(bold=True),
            height=32,
            fg_color=colors["surface_elevated"],
            text_color=colors["text_primary"],
            hover_color=colors["card_hover"],
            command=self._load_next_page
        )

    def refresh_all(self) -> None:
        """Reload stories tray and feed page 0."""
        self._load_stories()
        self._load_feed(page=0)

    def _load_stories(self) -> None:
        api = self.app_state.api if self.app_state else None
        if not api or self.is_loading_stories:
            return
        self.is_loading_stories = True

        def worker() -> Dict[str, Any]:
            return api.get_stories()

        def on_success(res: Dict[str, Any]) -> None:
            self.is_loading_stories = False
            self.story_groups = res.get("items", [])
            self._render_stories_tray()

        def on_error(exc: Exception) -> None:
            self.is_loading_stories = False
            logger.warning("Failed to fetch stories: %s", exc)

        run_async(worker, on_success=on_success, on_error=on_error)

    def _render_stories_tray(self) -> None:
        if not _HAS_CTK or not hasattr(self, "_stories_scroll"):
            return

        for child in self._stories_scroll.winfo_children():
            child.destroy()

        me_info = getattr(self.app_state, "current_user", None) or {}
        my_avatar = me_info.get("avatarUrl", "")

        # 1. "Your story" item
        my_group_idx = None
        for i, grp in enumerate(self.story_groups):
            if grp.get("user", {}).get("id") == me_info.get("id"):
                my_group_idx = i
                break

        has_my_unseen = False
        if my_group_idx is not None:
            has_my_unseen = self.story_groups[my_group_idx].get("hasUnseen", False)

        def on_my_story_clicked() -> None:
            if my_group_idx is not None:
                self._open_stories_viewer(my_group_idx)
            elif self.on_open_create_story:
                self.on_open_create_story()
            elif self.app_state and self.app_state.router:
                self.app_state.router.switch_tab("Create", initial_mode="Story")

        my_ring = StoryRing(
            self._stories_scroll,
            avatar_url=my_avatar,
            username="Your story",
            has_unseen=has_my_unseen,
            size=56,
            is_my_story=True,
            command=on_my_story_clicked,
            mode=self.mode
        )
        my_ring.pack(side="left", padx=(4, 6))

        # 2. Other Story Groups
        for idx, group in enumerate(self.story_groups):
            user = group.get("user", {})
            if user.get("id") == me_info.get("id"):
                continue

            ring = StoryRing(
                self._stories_scroll,
                avatar_url=user.get("avatarUrl", ""),
                username=user.get("username", "user"),
                has_unseen=group.get("hasUnseen", True),
                size=56,
                command=lambda i=idx: self._open_stories_viewer(i),
                mode=self.mode
            )
            ring.pack(side="left", padx=6)

    def _open_stories_viewer(self, group_idx: int) -> None:
        if not _HAS_CTK:
            return
        api = self.app_state.api if self.app_state else None
        player = self.app_state.player if self.app_state else None

        StoriesViewerModal(
            parent=self.winfo_toplevel(),
            story_groups=self.story_groups,
            initial_group_idx=group_idx,
            api=api,
            player=player,
            on_close=self._load_stories,
            mode=self.mode
        )

    def _load_feed(self, page: int = 0) -> None:
        api = self.app_state.api if self.app_state else None
        if not api or self.is_loading_feed:
            return
        self.is_loading_feed = True

        def worker() -> Dict[str, Any]:
            return api.get_feed(page=page, size=10)

        def on_success(res: Dict[str, Any]) -> None:
            self.is_loading_feed = False
            items = res.get("items", [])
            self.has_next_page = res.get("hasNext", False)
            self.current_page = page

            if page == 0:
                self.posts = items
                self._render_posts(clear=True)
                if not self.posts:
                    self._load_suggested_users()
                else:
                    self._hide_empty_state()
            else:
                self.posts.extend(items)
                self._render_posts(clear=False, new_items=items)

            self._update_load_more_button()

        def on_error(exc: Exception) -> None:
            self.is_loading_feed = False
            logger.warning("Failed to load feed: %s", exc)
            if _HAS_CTK:
                Toast.show(self.winfo_toplevel(), f"Feed error: {exc}", toast_type="error")

        run_async(worker, on_success=on_success, on_error=on_error)

    def _load_next_page(self) -> None:
        if self.has_next_page and not self.is_loading_feed:
            self._load_feed(page=self.current_page + 1)

    def _update_load_more_button(self) -> None:
        if not _HAS_CTK or not hasattr(self, "_load_more_btn"):
            return
        if self.has_next_page:
            self._load_more_btn.pack(pady=4)
        else:
            self._load_more_btn.pack_forget()

    def _render_posts(self, clear: bool = True, new_items: Optional[List[Dict[str, Any]]] = None) -> None:
        if not _HAS_CTK or not hasattr(self, "_posts_container"):
            return

        if clear:
            for child in self._posts_container.winfo_children():
                child.destroy()

        target_items = new_items if new_items is not None else self.posts
        api = self.app_state.api if self.app_state else None
        player = self.app_state.player if self.app_state else None

        for post_data in target_items:
            card = PostCard(
                self._posts_container,
                media_data=post_data,
                api=api,
                player=player,
                on_user_click=self._handle_user_clicked,
                on_comment_click=self._open_comments_modal,
                on_delete_success=self._handle_post_deleted,
                mode=self.mode
            )
            card.pack(fill="x", padx=4, pady=6)

    def _handle_post_deleted(self, media_id: int) -> None:
        self.posts = [p for p in self.posts if p.get("id") != media_id]
        if not self.posts:
            self._load_suggested_users()

    def _open_comments_modal(self, media_id: int) -> None:
        if not _HAS_CTK:
            return
        api = self.app_state.api if self.app_state else None
        CommentsModal(
            parent=self.winfo_toplevel(),
            media_id=media_id,
            api=api,
            mode=self.mode
        )

    def _load_suggested_users(self) -> None:
        api = self.app_state.api if self.app_state else None
        if not api:
            return

        def worker() -> Dict[str, Any]:
            return api.get_suggested_users()

        def on_success(res: Dict[str, Any]) -> None:
            self.suggested_users = res.get("items", [])
            self._render_empty_state()

        def on_error(exc: Exception) -> None:
            logger.warning("Failed to fetch suggested users: %s", exc)

        run_async(worker, on_success=on_success, on_error=on_error)

    def _render_empty_state(self) -> None:
        if not _HAS_CTK or not hasattr(self, "_empty_container"):
            return

        for child in self._empty_container.winfo_children():
            child.destroy()

        colors = get_theme_colors(self.mode)
        self._empty_container.pack(fill="x", padx=16, pady=20)

        title = ctk.CTkLabel(
            self._empty_container,
            text="Welcome to SocialApp!",
            font=font_h2(),
            text_color=colors["text_primary"]
        )
        title.pack(pady=(12, 4))

        sub = ctk.CTkLabel(
            self._empty_container,
            text="Follow people to see their photos and videos in your feed.",
            font=font_body(),
            text_color=colors["text_muted"],
            wraplength=360,
            justify="center"
        )
        sub.pack(pady=(0, 16))

        # Suggested Users Header
        sug_lbl = ctk.CTkLabel(
            self._empty_container,
            text="Suggested For You",
            font=font_caption(bold=True),
            text_color=colors["text_secondary"],
            anchor="w"
        )
        sug_lbl.pack(fill="x", padx=4, pady=(8, 4))

        api = self.app_state.api if self.app_state else None
        for user in self.suggested_users[:5]:
            row = UserRow(
                self._empty_container,
                user_summary=user,
                api=api,
                on_click=self._handle_user_clicked,
                mode=self.mode
            )
            row.pack(fill="x", pady=2)

    def _hide_empty_state(self) -> None:
        if _HAS_CTK and hasattr(self, "_empty_container"):
            self._empty_container.pack_forget()

    def _handle_user_clicked(self, user_id: int) -> None:
        if self.on_user_click:
            self.on_user_click(user_id)
        elif self.app_state and self.app_state.router:
            # Lazy import to avoid circular dependency
            from .profile import ProfileScreen
            self.app_state.router.push(
                ProfileScreen,
                title="Profile",
                app_state=self.app_state,
                user_id=user_id,
                mode=self.mode
            )

    def on_enter(self, **kwargs: Any) -> None:
        """Screen entered: refresh stories and feed."""
        if not self.posts:
            self.refresh_all()

    def on_leave(self) -> None:
        """Screen left: ensure any playing video stops."""
        if self.app_state and self.app_state.player:
            try:
                self.app_state.player.stop()
            except Exception:
                pass
