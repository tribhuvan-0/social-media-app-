"""
Profile Screen for SocialApp.
Renders user profile header (86px circular avatar, bio, follower/following stats),
follow/unfollow button with private account request handling, edit profile dialog with avatar upload,
follow requests badge, and a 3-column media grid with infinite scroll and post deletion.

API Calls:
- GET /api/users/{id}/profile -> Profile
- GET /api/users/{id}/posts?page=N&size=18 -> {items: GridItem[], hasNext}
- POST /api/users/{id}/follow, DELETE /api/users/{id}/follow
- PUT /api/users/me {bio, username} -> Me
- POST /api/uploads/presign (type=AVATAR) -> PUT binary -> PUT /api/users/me/avatar {r2Key}
- GET /api/follow-requests -> {items: UserSummary[], hasNext}
- DELETE /api/media/{id} -> 204
"""

import logging
import mimetypes
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..async_utils import run_async
from ..cache import load_image_async
from ..theme import (
    get_theme_colors,
    font_body,
    font_caption,
    font_h1,
    font_h2,
    font_small,
    RADIUS_BUTTON,
    RADIUS_CARD,
    RADIUS_ENTRY,
    style_primary_button,
    style_secondary_button,
    style_entry,
)
from ..widgets import AvatarView, ConfirmDialog, PostCard, Toast
from .follow_list import FollowListModal

from ..theme import UI_FONT

logger = logging.getLogger("SocialApp.screens.profile")

_HAS_CTK = False
try:
    import customtkinter as ctk
    from tkinter import filedialog
    _HAS_CTK = True
except Exception:
    ctk = None
    filedialog = None
    _HAS_CTK = False

_FrameBase = ctk.CTkFrame if _HAS_CTK else object


class ProfileScreen(_FrameBase):
    """
    Profile screen supporting both authenticated user's own profile and public/private profiles of others.
    """

    def __init__(
        self,
        master: Any,
        app_state: Any = None,
        user_id: Optional[int] = None,
        on_user_click: Optional[Callable[[int], None]] = None,
        mode: str = "dark",
        **kwargs: Any
    ) -> None:
        self.app_state = app_state
        self.target_user_id = user_id
        self.on_user_click = on_user_click
        self.mode = mode

        self.profile_data: Dict[str, Any] = {}
        self.grid_items: List[Dict[str, Any]] = []
        self.current_tab = "POSTS"  # "POSTS" or "REELS"
        self.current_page = 0
        self.has_next_page = False
        self.is_loading_profile = False
        self.is_loading_posts = False

        if _HAS_CTK:
            super().__init__(master, fg_color="transparent", **kwargs)
            self._build_ui()
        else:
            self._frame = None

    def _resolve_user_id(self) -> int:
        if self.target_user_id:
            return self.target_user_id
        if self.app_state and self.app_state.current_user:
            return self.app_state.current_user.get("id", 6)
        if self.app_state and hasattr(self.app_state.api, "_current_user_id"):
            return getattr(self.app_state.api, "_current_user_id", 6)
        return 6

    def _build_ui(self) -> None:
        if not _HAS_CTK:
            return

        colors = get_theme_colors(self.mode)

        # Scrollable Viewport
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True, padx=4, pady=0)

        # 1. Profile Header Container
        self._header_card = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._header_card.pack(fill="x", padx=12, pady=(10, 6))

        # Avatar & Stats Top Row
        top_row = ctk.CTkFrame(self._header_card, fg_color="transparent")
        top_row.pack(fill="x")

        self._avatar = AvatarView(top_row, size=80)
        self._avatar.pack(side="left", padx=(0, 16))

        # Stats Column: Posts, Followers, Following
        stats_frame = ctk.CTkFrame(top_row, fg_color="transparent")
        stats_frame.pack(side="left", fill="both", expand=True, pady=10)

        self._posts_stat_lbl = self._create_stat_widget(stats_frame, "0", "posts")
        self._followers_stat_lbl = self._create_stat_widget(
            stats_frame, "0", "followers",
            command=lambda: self._open_follow_list("followers")
        )
        self._following_stat_lbl = self._create_stat_widget(
            stats_frame, "0", "following",
            command=lambda: self._open_follow_list("following")
        )

        # Username & Bio
        self._username_lbl = ctk.CTkLabel(
            self._header_card,
            text="",
            font=font_h2(),
            text_color=colors["text_primary"],
            anchor="w"
        )
        self._username_lbl.pack(fill="x", pady=(8, 2))

        self._bio_lbl = ctk.CTkLabel(
            self._header_card,
            text="",
            font=font_body(),
            text_color=colors["text_secondary"],
            anchor="w",
            justify="left",
            wraplength=420
        )
        self._bio_lbl.pack(fill="x", pady=(0, 10))

        # Action Buttons Container (Edit Profile / Follow / Follow Requests)
        self._action_row = ctk.CTkFrame(self._header_card, fg_color="transparent")
        self._action_row.pack(fill="x", pady=(0, 6))

        # 2. Private Account Lock Screen
        self._lock_card = ctk.CTkFrame(self._scroll, fg_color="transparent")

        lock_icon = ctk.CTkLabel(
            self._lock_card,
            text="🔒",
            font=(UI_FONT, 36),
            text_color=colors["text_muted"]
        )
        lock_icon.pack(pady=(30, 8))

        lock_title = ctk.CTkLabel(
            self._lock_card,
            text="This Account is Private",
            font=font_h2(),
            text_color=colors["text_primary"]
        )
        lock_title.pack(pady=(0, 4))

        lock_sub = ctk.CTkLabel(
            self._lock_card,
            text="Follow this account to see their photos and videos.",
            font=font_body(),
            text_color=colors["text_muted"]
        )
        lock_sub.pack(pady=(0, 30))

        # 3. Tab Selector (Posts / Reels)
        self._tab_bar = ctk.CTkSegmentedButton(
            self._scroll,
            values=["Posts", "Reels"],
            command=self._on_tab_changed,
            font=font_caption(bold=True),
            fg_color=colors["surface_elevated"],
            selected_color=colors["primary"],
            selected_hover_color=colors["primary_hover"],
            corner_radius=RADIUS_BUTTON
        )
        self._tab_bar.set("Posts")
        self._tab_bar.pack(fill="x", padx=12, pady=(4, 8))

        # 4. 3-Column Media Grid
        self._grid_frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._grid_frame.pack(fill="both", expand=True, padx=4)

        # 5. Load More Button
        self._load_more_btn = ctk.CTkButton(
            self._scroll,
            text="Load more posts",
            font=font_caption(bold=True),
            height=32,
            fg_color=colors["surface_elevated"],
            text_color=colors["text_primary"],
            hover_color=colors["card_hover"],
            command=self._load_next_posts_page
        )

    def _create_stat_widget(
        self,
        parent: Any,
        initial_val: str,
        label_text: str,
        command: Optional[Callable[[], None]] = None
    ) -> Any:
        colors = get_theme_colors(self.mode)
        col = ctk.CTkFrame(parent, fg_color="transparent")
        col.pack(side="left", expand=True, fill="both")

        num_lbl = ctk.CTkLabel(
            col,
            text=initial_val,
            font=font_body(bold=True),
            text_color=colors["text_primary"]
        )
        num_lbl.pack()

        desc_lbl = ctk.CTkLabel(
            col,
            text=label_text,
            font=font_caption(),
            text_color=colors["text_muted"]
        )
        desc_lbl.pack()

        if command:
            num_lbl.configure(cursor="hand2")
            desc_lbl.configure(cursor="hand2")
            num_lbl.bind("<Button-1>", lambda e: command())
            desc_lbl.bind("<Button-1>", lambda e: command())

        return num_lbl

    def load_profile(self) -> None:
        api = self.app_state.api if self.app_state else None
        if not api or self.is_loading_profile:
            return
        self.is_loading_profile = True

        uid = self._resolve_user_id()

        def worker() -> Dict[str, Any]:
            return api.get_profile(uid)

        def on_success(profile: Dict[str, Any]) -> None:
            self.is_loading_profile = False
            self.profile_data = profile
            self._render_profile_header()

            can_view = bool(profile.get("canView", True))
            if can_view:
                self._hide_lock()
                self._load_posts(page=0)
            else:
                self._show_lock()

        def on_error(exc: Exception) -> None:
            self.is_loading_profile = False
            logger.warning("Failed to load profile for user %s: %s", uid, exc)

        run_async(worker, on_success=on_success, on_error=on_error)

    def _render_profile_header(self) -> None:
        if not _HAS_CTK:
            return

        colors = get_theme_colors(self.mode)
        p = self.profile_data

        username = p.get("username", "user")
        avatar_url = p.get("avatarUrl", "")
        bio = p.get("bio", "")
        post_count = p.get("postCount", 0)
        follower_count = p.get("followerCount", 0)
        following_count = p.get("followingCount", 0)
        is_me = bool(p.get("isMe", False))
        followed_by_me = bool(p.get("followedByMe", False))
        requested_by_me = bool(p.get("requestedByMe", False))

        self._username_lbl.configure(text=f"@{username}")
        self._bio_lbl.configure(text=bio if bio else "No bio yet.")
        self._avatar.set_image(avatar_url)

        self._posts_stat_lbl.configure(text=str(post_count))
        self._followers_stat_lbl.configure(text=str(follower_count))
        self._following_stat_lbl.configure(text=str(following_count))

        # Clear action row
        for child in self._action_row.winfo_children():
            child.destroy()

        if is_me:
            # Edit Profile Button
            edit_btn = ctk.CTkButton(
                self._action_row,
                text="Edit Profile",
                font=font_caption(bold=True),
                height=32,
                corner_radius=RADIUS_BUTTON,
                fg_color=colors["surface_elevated"],
                text_color=colors["text_primary"],
                hover_color=colors["card_hover"],
                command=self._open_edit_profile_dialog
            )
            edit_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))

            # Settings Button (⚙)
            settings_btn = ctk.CTkButton(
                self._action_row,
                text="⚙",
                width=34,
                height=32,
                font=(UI_FONT, 16),
                corner_radius=RADIUS_BUTTON,
                fg_color=colors["surface_elevated"],
                text_color=colors["text_primary"],
                hover_color=colors["card_hover"],
                command=self._open_settings_screen
            )
            settings_btn.pack(side="left", padx=(0, 6))

            # Follow Requests Button (with badge)
            self._load_follow_requests_badge()
        else:
            # Follow / Following / Requested button
            self._follow_btn = ctk.CTkButton(
                self._action_row,
                text="Following" if followed_by_me else ("Requested" if requested_by_me else "Follow"),
                font=font_caption(bold=True),
                height=32,
                corner_radius=RADIUS_BUTTON,
                fg_color=colors["surface_elevated"] if (followed_by_me or requested_by_me) else colors["primary"],
                text_color=colors["text_primary"] if (followed_by_me or requested_by_me) else "#FFFFFF",
                hover_color=colors["card_hover"] if (followed_by_me or requested_by_me) else colors["primary_hover"],
                command=self._toggle_follow_user
            )
            self._follow_btn.pack(fill="x", expand=True)

    def _load_follow_requests_badge(self) -> None:
        api = self.app_state.api if self.app_state else None
        if not api:
            return

        def worker() -> Dict[str, Any]:
            return api.get_follow_requests(page=0, size=20)

        def on_success(res: Dict[str, Any]) -> None:
            items = res.get("items", [])
            if items and _HAS_CTK and hasattr(self, "_action_row"):
                colors = get_theme_colors(self.mode)
                req_btn = ctk.CTkButton(
                    self._action_row,
                    text=f"Requests ({len(items)})",
                    font=font_caption(bold=True),
                    height=32,
                    corner_radius=RADIUS_BUTTON,
                    fg_color=colors["primary"],
                    text_color="#FFFFFF",
                    hover_color=colors["primary_hover"],
                    command=self._open_activity_screen
                )
                req_btn.pack(side="right", padx=(6, 0))

        run_async(worker, on_success=on_success)

    def _open_activity_screen(self) -> None:
        if self.app_state and self.app_state.router:
            from .activity import ActivityScreen
            self.app_state.router.push(ActivityScreen, title="Activity", app_state=self.app_state, mode=self.mode)

    def _open_settings_screen(self) -> None:
        if self.app_state and self.app_state.router:
            from .settings import SettingsScreen
            self.app_state.router.push(SettingsScreen, title="Settings", app_state=self.app_state, mode=self.mode)

    def _toggle_follow_user(self) -> None:
        api = self.app_state.api if self.app_state else None
        if not api or not self.profile_data:
            return

        uid = self.profile_data.get("id", 0)
        followed = bool(self.profile_data.get("followedByMe", False))
        requested = bool(self.profile_data.get("requestedByMe", False))

        if followed:
            # Confirm prompt for unfollow
            ConfirmDialog(
                self.winfo_toplevel(),
                title="Unfollow",
                message=f"Unfollow @{self.profile_data.get('username')}?",
                confirm_text="Unfollow",
                on_confirm=lambda: self._execute_follow_action(unfollow=True)
            )
        else:
            self._execute_follow_action(unfollow=False)

    def _execute_follow_action(self, unfollow: bool) -> None:
        api = self.app_state.api
        uid = self.profile_data.get("id", 0)

        def worker() -> Dict[str, Any]:
            if unfollow:
                return api.unfollow_user(uid)
            else:
                return api.follow_user(uid)

        def on_success(res: Dict[str, Any]) -> None:
            self.profile_data["followedByMe"] = res.get("following", False)
            self.profile_data["requestedByMe"] = res.get("requested", False)
            if "followerCount" in res:
                self.profile_data["followerCount"] = res["followerCount"]
            self._render_profile_header()

            # Refresh canView check
            if not res.get("following", False) and self.profile_data.get("isPrivate"):
                self.profile_data["canView"] = False
                self._show_lock()
            else:
                self.profile_data["canView"] = True
                self._hide_lock()
                self._load_posts(page=0)

        run_async(worker, on_success=on_success)

    def _show_lock(self) -> None:
        if not _HAS_CTK:
            return
        self._tab_bar.pack_forget()
        self._grid_frame.pack_forget()
        self._load_more_btn.pack_forget()
        self._lock_card.pack(fill="x", pady=20)

    def _hide_lock(self) -> None:
        if not _HAS_CTK:
            return
        self._lock_card.pack_forget()
        self._tab_bar.pack(fill="x", padx=12, pady=(4, 8))
        self._grid_frame.pack(fill="both", expand=True, padx=4)

    def _on_tab_changed(self, value: str) -> None:
        self.current_tab = value.upper()
        self._render_grid()

    def _load_posts(self, page: int = 0) -> None:
        api = self.app_state.api if self.app_state else None
        if not api or self.is_loading_posts:
            return
        self.is_loading_posts = True

        uid = self._resolve_user_id()

        def worker() -> Dict[str, Any]:
            return api.get_user_posts(uid, page=page, size=18)

        def on_success(res: Dict[str, Any]) -> None:
            self.is_loading_posts = False
            items = res.get("items", [])
            self.has_next_page = res.get("hasNext", False)
            self.current_page = page

            if page == 0:
                self.grid_items = items
            else:
                self.grid_items.extend(items)

            self._render_grid()
            self._update_load_more_button()

        def on_error(exc: Exception) -> None:
            self.is_loading_posts = False
            logger.warning("Failed to fetch posts: %s", exc)

        run_async(worker, on_success=on_success, on_error=on_error)

    def _load_next_posts_page(self) -> None:
        if self.has_next_page and not self.is_loading_posts:
            self._load_posts(page=self.current_page + 1)

    def _update_load_more_button(self) -> None:
        if not _HAS_CTK or not hasattr(self, "_load_more_btn"):
            return
        if self.has_next_page:
            self._load_more_btn.pack(pady=10)
        else:
            self._load_more_btn.pack_forget()

    def _render_grid(self) -> None:
        if not _HAS_CTK or not hasattr(self, "_grid_frame"):
            return

        for child in self._grid_frame.winfo_children():
            child.destroy()

        colors = get_theme_colors(self.mode)

        # Filter by tab
        if self.current_tab == "REELS":
            visible_items = [m for m in self.grid_items if m.get("type") == "REEL" or m.get("mediaKind") == "VIDEO"]
        else:
            visible_items = [m for m in self.grid_items if m.get("type") == "POST"]

        if not visible_items:
            empty_lbl = ctk.CTkLabel(
                self._grid_frame,
                text=f"No {self.current_tab.lower()} yet.",
                font=font_body(),
                text_color=colors["text_muted"]
            )
            empty_lbl.pack(pady=40)
            return

        col_width = 146
        col_height = 146

        for i, item in enumerate(visible_items):
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

            thumb_lbl = ctk.CTkLabel(cell, text="")
            thumb_lbl.place(relx=0, rely=0, relwidth=1.0, relheight=1.0)

            thumb_url = item.get("thumbnailUrl") or item.get("mediaUrl", "")

            def on_ready(wrapped: Any, lbl=thumb_lbl) -> None:
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
            thumb_lbl.configure(image=placeholder)

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

            # Click thumbnail opens full detail view
            mid = item.get("id", 0)
            thumb_lbl.bind("<Button-1>", lambda e, media_id=mid: self._open_detail_modal(media_id))

    def _safe_grab_dlg(self, dlg: Any) -> None:
        try:
            if dlg.winfo_exists():
                dlg.grab_set()
        except Exception:
            pass

    def _open_detail_modal(self, media_id: int) -> None:
        if not _HAS_CTK:
            return
        api = self.app_state.api if self.app_state else None
        if not api:
            return

        def fetch_worker() -> Dict[str, Any]:
            return api.get_media(media_id)

        def on_fetched(media_data: Dict[str, Any]) -> None:
            parent = self.winfo_toplevel()
            dlg = ctk.CTkToplevel(parent)
            dlg.title("Media Detail")
            dlg.geometry("460x720")
            dlg.resizable(False, False)
            dlg.transient(parent)
            dlg.after(100, lambda: self._safe_grab_dlg(dlg))

            colors = get_theme_colors(self.mode)
            dlg.configure(fg_color=colors["bg"])

            card = PostCard(
                dlg,
                media_data=media_data,
                api=api,
                player=self.app_state.player if self.app_state else None,
                on_delete_success=lambda mid: [dlg.destroy(), self._handle_item_deleted(mid)],
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

        run_async(fetch_worker, on_success=on_fetched)

    def _handle_item_deleted(self, media_id: int) -> None:
        self.grid_items = [item for item in self.grid_items if item.get("id") != media_id]
        if "postCount" in self.profile_data:
            self.profile_data["postCount"] = max(0, self.profile_data["postCount"] - 1)
            self._posts_stat_lbl.configure(text=str(self.profile_data["postCount"]))
        self._render_grid()

    def _open_follow_list(self, list_type: str) -> None:
        if not _HAS_CTK:
            return
        FollowListModal(
            parent=self.winfo_toplevel(),
            user_id=self._resolve_user_id(),
            list_type=list_type,
            api=self.app_state.api if self.app_state else None,
            on_user_click=self._handle_user_selected,
            mode=self.mode
        )

    def _handle_user_selected(self, uid: int) -> None:
        if self.on_user_click:
            self.on_user_click(uid)
        elif self.app_state and self.app_state.router:
            self.app_state.router.push(
                ProfileScreen,
                title="Profile",
                app_state=self.app_state,
                user_id=uid,
                mode=self.mode
            )

    def _open_edit_profile_dialog(self) -> None:
        if not _HAS_CTK:
            return

        parent = self.winfo_toplevel()
        dlg = ctk.CTkToplevel(parent)
        dlg.title("Edit Profile")
        dlg.geometry("380x420")
        dlg.resizable(False, False)
        dlg.transient(parent)
        dlg.after(100, lambda: self._safe_grab_dlg(dlg))

        colors = get_theme_colors(self.mode)
        dlg.configure(fg_color=colors["surface"])

        title = ctk.CTkLabel(dlg, text="Edit Profile", font=font_h2(), text_color=colors["text_primary"])
        title.pack(pady=(16, 12))

        # Change Photo Button
        change_photo_btn = ctk.CTkButton(
            dlg,
            text="📷 Change Profile Photo",
            font=font_caption(bold=True),
            height=34,
            corner_radius=RADIUS_BUTTON,
            fg_color=colors["surface_elevated"],
            text_color=colors["primary"],
            hover_color=colors["card_hover"],
            command=lambda: self._upload_avatar(dlg)
        )
        change_photo_btn.pack(fill="x", padx=30, pady=(0, 14))

        # Username Field
        un_lbl = ctk.CTkLabel(dlg, text="Username", font=font_caption(bold=True), text_color=colors["text_secondary"], anchor="w")
        un_lbl.pack(fill="x", padx=30)

        un_entry = ctk.CTkEntry(dlg, height=38, corner_radius=RADIUS_ENTRY, font=font_body())
        style_entry(un_entry, self.mode)
        un_entry.insert(0, self.profile_data.get("username", ""))
        un_entry.pack(fill="x", padx=30, pady=(2, 12))

        # Bio Field
        bio_lbl = ctk.CTkLabel(dlg, text="Bio", font=font_caption(bold=True), text_color=colors["text_secondary"], anchor="w")
        bio_lbl.pack(fill="x", padx=30)

        bio_entry = ctk.CTkTextbox(dlg, height=80, corner_radius=RADIUS_ENTRY, font=font_body())
        bio_entry.insert("1.0", self.profile_data.get("bio", ""))
        bio_entry.pack(fill="x", padx=30, pady=(2, 16))

        # Save Button
        save_btn = ctk.CTkButton(
            dlg,
            text="Save Changes",
            height=38,
            font=font_body(bold=True),
            corner_radius=RADIUS_BUTTON,
            command=lambda: self._save_profile_edits(dlg, un_entry.get().strip(), bio_entry.get("1.0", "end-1c").strip())
        )
        style_primary_button(save_btn, self.mode)
        save_btn.pack(fill="x", padx=30)

    def _save_profile_edits(self, dlg: Any, new_un: str, new_bio: str) -> None:
        api = self.app_state.api if self.app_state else None
        if not api:
            return

        def worker() -> Dict[str, Any]:
            return api.update_profile(bio=new_bio, username=new_un if new_un else None)

        def on_success(me: Dict[str, Any]) -> None:
            if self.app_state:
                self.app_state.current_user = me
            self.profile_data["username"] = me.get("username", new_un)
            self.profile_data["bio"] = me.get("bio", new_bio)
            self._username_lbl.configure(text=f"@{self.profile_data['username']}")
            self._bio_lbl.configure(text=self.profile_data["bio"])
            dlg.destroy()
            Toast.show(self.winfo_toplevel(), "Profile updated!", toast_type="success")

        def on_error(exc: Exception) -> None:
            Toast.show(dlg, f"Update failed: {exc}", toast_type="error")

        run_async(worker, on_success=on_success, on_error=on_error)

    def _upload_avatar(self, parent_dlg: Any) -> None:
        if not filedialog:
            return
        chosen = filedialog.askopenfilename(
            title="Choose Avatar Image",
            filetypes=[("Image Files", "*.jpg *.jpeg *.png")]
        )
        if not chosen:
            return

        api = self.app_state.api if self.app_state else None
        if not api:
            return

        p = Path(chosen)
        file_size = p.stat().st_size
        mime, _ = mimetypes.guess_type(chosen)
        content_type = mime or "image/jpeg"

        def avatar_flow() -> Dict[str, Any]:
            presign = api.presign_upload(p.name, content_type, "AVATAR", file_size)
            upload_url = presign.get("uploadUrl")
            r2_key = presign.get("r2Key")
            api.upload_file_binary(upload_url, chosen, content_type)
            return api.update_avatar(r2_key)

        def on_success(me: Dict[str, Any]) -> None:
            if self.app_state:
                self.app_state.current_user = me
            self.profile_data["avatarUrl"] = me.get("avatarUrl", "")
            self._avatar.set_image(self.profile_data["avatarUrl"])
            Toast.show(parent_dlg, "Avatar updated!", toast_type="success")

        def on_error(exc: Exception) -> None:
            Toast.show(parent_dlg, f"Avatar upload failed: {exc}", toast_type="error")

        run_async(avatar_flow, on_success=on_success, on_error=on_error)

    def on_enter(self, **kwargs: Any) -> None:
        target = kwargs.get("user_id")
        if target:
            self.target_user_id = target
        self.load_profile()

    def on_leave(self) -> None:
        pass
