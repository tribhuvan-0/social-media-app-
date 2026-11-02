"""
Comments Modal Dialog for SocialApp.
Displays paginated list of comments for a specific post/reel, allows author or media owner
to delete comments, and supports submitting new comments with character limits.

API Calls:
- GET /api/media/{id}/comments?page=N&size=20 -> {items: Comment[], hasNext}
- POST /api/media/{id}/comments {text} -> 201 Comment
- DELETE /api/comments/{id} -> 204
"""

import logging
from typing import Any, Callable, Dict, List, Optional

from ..async_utils import run_async
from ..theme import (
    get_theme_colors,
    font_body,
    font_caption,
    font_h2,
    RADIUS_CARD,
    RADIUS_BUTTON,
    RADIUS_ENTRY,
    style_primary_button,
    style_entry,
)
from ..widgets import AvatarView, ConfirmDialog, Toast, format_relative_time

from ..theme import UI_FONT
from ..anim import fade_in_window, pop_button

logger = logging.getLogger("SocialApp.screens.comments")

_HAS_CTK = False
try:
    import customtkinter as ctk
    _HAS_CTK = True
except Exception:
    ctk = None
    _HAS_CTK = False

_ToplevelBase = ctk.CTkToplevel if _HAS_CTK else object


class CommentsModal(_ToplevelBase):
    """
    Modal window displaying media comments with paginated fetch, add comment, and delete comment actions.
    """

    def __init__(
        self,
        parent: Any,
        media_id: int,
        api: Any,
        media_owner_id: Optional[int] = None,
        on_comment_count_change: Optional[Callable[[int], None]] = None,
        mode: str = "dark",
        **kwargs: Any
    ) -> None:
        self.media_id = media_id
        self.api = api
        self.media_owner_id = media_owner_id
        self.on_comment_count_change = on_comment_count_change
        self.mode = mode

        self.comments: List[Dict[str, Any]] = []
        self.current_page = 0
        self.has_next = False
        self.is_loading = False

        if _HAS_CTK and parent is not None:
            super().__init__(parent)
            self.title("Comments")
            self.geometry("420x600")
            self.resizable(False, False)
            self.transient(parent)
            self.after(100, self._safe_grab)
            fade_in_window(self)

            colors = get_theme_colors(mode)
            self.configure(fg_color=colors["surface"])

            # Center on parent
            try:
                x = parent.winfo_x() + (parent.winfo_width() - 420) // 2
                y = parent.winfo_y() + (parent.winfo_height() - 600) // 2
                self.geometry(f"+{max(0, x)}+{max(0, y)}")
            except Exception:
                pass

            self._build_ui()
            self._load_comments(page=0)
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

        colors = get_theme_colors(self.mode)

        # Header Frame
        header = ctk.CTkFrame(self, height=48, fg_color=colors["surface"], corner_radius=0)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        title_lbl = ctk.CTkLabel(
            header,
            text="Comments",
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

        # Bottom Input Bar
        input_container = ctk.CTkFrame(self, height=60, fg_color=colors["surface"], corner_radius=0)
        input_container.pack(fill="x", side="bottom")
        input_container.pack_propagate(False)

        top_div = ctk.CTkFrame(input_container, height=1, fg_color=colors["divider"])
        top_div.pack(fill="x", side="top")

        input_box = ctk.CTkFrame(input_container, fg_color="transparent")
        input_box.pack(fill="both", expand=True, padx=12, pady=8)

        self._entry = ctk.CTkEntry(
            input_box,
            placeholder_text="Add a comment… (max 500 chars)",
            height=38,
            corner_radius=RADIUS_ENTRY,
            font=font_body()
        )
        style_entry(self._entry, self.mode)
        self._entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._entry.bind("<Return>", lambda e: self._submit_comment())

        self._post_btn = ctk.CTkButton(
            input_box,
            text="Post",
            width=64,
            height=38,
            font=font_body(bold=True),
            corner_radius=RADIUS_BUTTON,
            command=self._submit_comment
        )
        style_primary_button(self._post_btn, self.mode)
        self._post_btn.pack(side="right")

        # Scrollable Comments List
        self._scroll_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent"
        )
        self._scroll_frame.pack(fill="both", expand=True, padx=8, pady=4)

        # Empty State Label
        self._empty_label = ctk.CTkLabel(
            self._scroll_frame,
            text="No comments yet.\nBe the first to comment!",
            font=font_body(),
            text_color=colors["text_muted"],
            justify="center"
        )

    def _close(self) -> None:
        if _HAS_CTK:
            try:
                self.grab_release()
                self.destroy()
            except Exception:
                pass

    def _load_comments(self, page: int = 0) -> None:
        if self.is_loading:
            return
        self.is_loading = True

        def worker() -> Dict[str, Any]:
            return self.api.get_comments(self.media_id, page=page, size=20)

        def on_success(res: Dict[str, Any]) -> None:
            self.is_loading = False
            items = res.get("items", [])
            self.has_next = res.get("hasNext", False)
            self.current_page = page

            if page == 0:
                self.comments = items
                self._render_comments(clear=True)
            else:
                self.comments.extend(items)
                self._render_comments(clear=False, new_items=items)

        def on_error(exc: Exception) -> None:
            self.is_loading = False
            logger.warning("Failed to load comments: %s", exc)
            if _HAS_CTK:
                Toast.show(self, f"Failed to load comments: {exc}", toast_type="error")

        run_async(worker, on_success=on_success, on_error=on_error)

    def _render_comments(self, clear: bool = True, new_items: Optional[List[Dict[str, Any]]] = None) -> None:
        if not _HAS_CTK or not hasattr(self, "_scroll_frame"):
            return

        if clear:
            for child in self._scroll_frame.winfo_children():
                child.destroy()

        target_list = new_items if new_items is not None else self.comments

        if not self.comments:
            self._empty_label = ctk.CTkLabel(
                self._scroll_frame,
                text="No comments yet.\nBe the first to comment!",
                font=font_body(),
                text_color=get_theme_colors(self.mode)["text_muted"],
                justify="center"
            )
            self._empty_label.pack(pady=40)
            return

        for comment in target_list:
            self._add_comment_row(comment)

        # If has_next, add "Load more" button
        if self.has_next:
            more_btn = ctk.CTkButton(
                self._scroll_frame,
                text="Load more comments",
                font=font_caption(bold=True),
                height=30,
                fg_color="transparent",
                text_color=get_theme_colors(self.mode)["primary"],
                hover_color=get_theme_colors(self.mode)["surface_elevated"],
                command=lambda: self._load_comments(page=self.current_page + 1)
            )
            more_btn.pack(pady=8)

    def _add_comment_row(self, comment: Dict[str, Any]) -> None:
        colors = get_theme_colors(self.mode)
        cid = comment.get("id", 0)
        user = comment.get("user", {})
        uid = user.get("id", 0)
        username = user.get("username", "user")
        avatar_url = user.get("avatarUrl", "")
        text = comment.get("text", "")
        created_at = comment.get("createdAt", "")

        row = ctk.CTkFrame(self._scroll_frame, fg_color="transparent")
        row.pack(fill="x", padx=4, pady=6)

        # Avatar
        av = AvatarView(row, image_url_or_path=avatar_url, size=32)
        av.pack(side="left", padx=(0, 8), anchor="n")

        # Content frame
        content = ctk.CTkFrame(row, fg_color="transparent")
        content.pack(side="left", fill="both", expand=True)

        user_line = ctk.CTkFrame(content, fg_color="transparent")
        user_line.pack(fill="x", anchor="w")

        name_lbl = ctk.CTkLabel(
            user_line,
            text=username,
            font=font_body(bold=True),
            text_color=colors["text_primary"],
            anchor="w"
        )
        name_lbl.pack(side="left", padx=(0, 6))

        time_lbl = ctk.CTkLabel(
            user_line,
            text=format_relative_time(created_at),
            font=font_caption(),
            text_color=colors["text_muted"],
            anchor="w"
        )
        time_lbl.pack(side="left")

        text_lbl = ctk.CTkLabel(
            content,
            text=text,
            font=font_body(),
            text_color=colors["text_primary"],
            anchor="w",
            justify="left",
            wraplength=280
        )
        text_lbl.pack(fill="x", anchor="w", pady=(2, 0))

        # Check delete permission: comment author OR media owner
        me_id = getattr(self.api, "_current_user_id", None)
        can_delete = (uid == me_id) or (self.media_owner_id == me_id)

        if can_delete:
            del_btn = ctk.CTkButton(
                row,
                text="🗑",
                width=24,
                height=24,
                font=(UI_FONT, 12),
                fg_color="transparent",
                text_color=colors["text_muted"],
                hover_color=colors["surface_elevated"],
                command=lambda cid=cid, row_widget=row: self._confirm_delete(cid, row_widget)
            )
            del_btn.pack(side="right", padx=4, anchor="n")

    def _confirm_delete(self, comment_id: int, row_widget: Any) -> None:
        ConfirmDialog(
            self,
            title="Delete Comment",
            message="Delete this comment? This cannot be undone.",
            confirm_text="Delete",
            on_confirm=lambda: self._delete_comment(comment_id, row_widget)
        )

    def _delete_comment(self, comment_id: int, row_widget: Any) -> None:
        def worker() -> None:
            self.api.delete_comment(comment_id)

        def on_success(_: Any) -> None:
            if _HAS_CTK:
                try:
                    row_widget.destroy()
                except Exception:
                    pass
            self.comments = [c for c in self.comments if c.get("id") != comment_id]
            if self.on_comment_count_change:
                self.on_comment_count_change(len(self.comments))

        def on_error(exc: Exception) -> None:
            logger.warning("Failed to delete comment: %s", exc)
            if _HAS_CTK:
                Toast.show(self, f"Could not delete comment: {exc}", toast_type="error")

        run_async(worker, on_success=on_success, on_error=on_error)

    def _submit_comment(self) -> None:
        if not _HAS_CTK or not hasattr(self, "_entry"):
            return

        text = self._entry.get().strip()
        if not text:
            return
        if len(text) > 500:
            Toast.show(self, "Comment cannot exceed 500 characters.", toast_type="error")
            return

        self._entry.delete(0, "end")
        self._post_btn.configure(state="disabled")

        def worker() -> Dict[str, Any]:
            return self.api.add_comment(self.media_id, text=text)

        def on_success(new_c: Dict[str, Any]) -> None:
            self._post_btn.configure(state="normal")
            self.comments.append(new_c)
            if hasattr(self, "_empty_label"):
                try:
                    self._empty_label.destroy()
                except Exception:
                    pass
            self._add_comment_row(new_c)
            if self.on_comment_count_change:
                self.on_comment_count_change(len(self.comments))

        def on_error(exc: Exception) -> None:
            self._post_btn.configure(state="normal")
            logger.warning("Failed to post comment: %s", exc)
            Toast.show(self, f"Could not post comment: {exc}", toast_type="error")

        run_async(worker, on_success=on_success, on_error=on_error)
