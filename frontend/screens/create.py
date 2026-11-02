"""
Create and Upload Media Screen for SocialApp.
Supports creating Posts, Reels, and Stories with file picker validation (.jpg, .png, .mp4),
file size verification (10MB image, 100MB video), real-time hashtag chip extraction,
interactive preview, streaming binary upload progress, and confirm flow.

API Calls:
- POST /api/uploads/presign {fileName, contentType, type, fileSize} -> {uploadUrl, r2Key}
- PUT binary data to uploadUrl (no Auth header)
- POST /api/uploads/confirm {r2Key, type, caption} -> 201 MediaCard
"""

import logging
import mimetypes
import os
from pathlib import Path
import re
from typing import Any, Callable, Dict, List, Optional

from PIL import Image

from ..async_utils import run_async
from ..cache import wrap_image
from ..theme import (
    get_theme_colors,
    font_body,
    font_caption,
    font_h2,
    font_small,
    RADIUS_BUTTON,
    RADIUS_CARD,
    RADIUS_ENTRY,
    RADIUS_CHIP,
    style_primary_button,
    style_entry,
)
from ..widgets import Toast

logger = logging.getLogger("SocialApp.screens.create")

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


class CreateScreen(_FrameBase):
    """
    Create / Upload Screen handling Post, Reel, and Story uploads.
    """

    MAX_IMAGE_SIZE = 10 * 1024 * 1024   # 10 MB
    MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100 MB
    MAX_CAPTION_LEN = 2200

    def __init__(
        self,
        master: Any,
        app_state: Any = None,
        initial_mode: str = "Post",
        mode: str = "dark",
        **kwargs: Any
    ) -> None:
        self.app_state = app_state
        self.mode = mode
        self.media_type = initial_mode.upper() if initial_mode.upper() in ("POST", "REEL", "STORY") else "POST"

        self.selected_file_path: Optional[str] = None
        self.file_size = 0
        self.content_type = ""
        self.is_uploading = False
        self._cancel_requested = False

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
            text="Create New Media",
            font=font_h2(),
            text_color=colors["text_primary"]
        )
        title_lbl.pack(pady=(12, 8))

        # Mode Selector: Post / Reel / Story
        self._type_selector = ctk.CTkSegmentedButton(
            self,
            values=["Post", "Reel", "Story"],
            command=self._on_type_changed,
            font=font_body(bold=True),
            fg_color=colors["surface_elevated"],
            selected_color=colors["primary"],
            selected_hover_color=colors["primary_hover"],
            corner_radius=RADIUS_BUTTON
        )
        display_type = self.media_type.capitalize()
        self._type_selector.set(display_type)
        self._type_selector.pack(fill="x", padx=20, pady=(0, 12))

        # Scrollable form container
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True, padx=8, pady=0)

        # 1. File Picker & Preview Area
        self._preview_card = ctk.CTkFrame(
            self._scroll,
            height=240,
            fg_color=colors["surface"],
            corner_radius=RADIUS_CARD,
            border_width=1,
            border_color=colors["border"]
        )
        self._preview_card.pack(fill="x", padx=12, pady=(0, 10))
        self._preview_card.pack_propagate(False)

        self._preview_label = ctk.CTkLabel(
            self._preview_card,
            text="No media selected\n\nChoose an image or video to preview",
            font=font_body(),
            text_color=colors["text_muted"],
            justify="center"
        )
        self._preview_label.place(relx=0.5, rely=0.45, anchor="center")

        self._choose_btn = ctk.CTkButton(
            self._preview_card,
            text="📁 Choose File",
            font=font_caption(bold=True),
            height=32,
            corner_radius=RADIUS_BUTTON,
            fg_color=colors["surface_elevated"],
            text_color=colors["text_primary"],
            hover_color=colors["card_hover"],
            command=self._choose_file
        )
        self._choose_btn.place(relx=0.5, rely=0.82, anchor="center")

        # 2. Reel Hint (conditional)
        self._reel_hint_lbl = ctk.CTkLabel(
            self._scroll,
            text="💡 Tip: Add #hashtags so people with similar interests discover your reel!",
            font=font_caption(),
            text_color=colors["primary"],
            wraplength=400,
            justify="left"
        )

        # 3. Caption Box & Counter
        self._caption_container = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._caption_container.pack(fill="x", padx=12, pady=(0, 8))

        cap_header = ctk.CTkFrame(self._caption_container, fg_color="transparent")
        cap_header.pack(fill="x", pady=(0, 4))

        cap_title = ctk.CTkLabel(
            cap_header,
            text="Caption",
            font=font_caption(bold=True),
            text_color=colors["text_secondary"]
        )
        cap_title.pack(side="left")

        self._char_counter = ctk.CTkLabel(
            cap_header,
            text=f"0 / {self.MAX_CAPTION_LEN}",
            font=font_small(),
            text_color=colors["text_muted"]
        )
        self._char_counter.pack(side="right")

        self._caption_box = ctk.CTkTextbox(
            self._caption_container,
            height=90,
            corner_radius=RADIUS_ENTRY,
            font=font_body(),
            fg_color=colors["surface"],
            border_width=1,
            border_color=colors["border"]
        )
        self._caption_box.pack(fill="x")
        self._caption_box.bind("<KeyRelease>", lambda e: self._on_caption_changed())

        # Detected Hashtag Chips Row
        self._tags_container = ctk.CTkFrame(self._caption_container, fg_color="transparent")
        self._tags_container.pack(fill="x", pady=(6, 0))

        # 4. Upload Progress & Status
        self._progress_bar = ctk.CTkProgressBar(
            self._scroll,
            height=6,
            corner_radius=3,
            fg_color=colors["surface_elevated"],
            progress_color=colors["primary"]
        )
        self._progress_bar.set(0)

        self._status_label = ctk.CTkLabel(
            self._scroll,
            text="",
            font=font_caption(),
            text_color=colors["text_secondary"]
        )

        # 5. Action Buttons (Share / Cancel)
        self._btn_row = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._btn_row.pack(fill="x", padx=12, pady=(10, 20))

        self._share_btn = ctk.CTkButton(
            self._btn_row,
            text="Share Post",
            height=42,
            font=font_body(bold=True),
            corner_radius=RADIUS_BUTTON,
            command=self._submit_upload
        )
        style_primary_button(self._share_btn, self.mode)
        self._share_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self._cancel_btn = ctk.CTkButton(
            self._btn_row,
            text="Cancel",
            height=42,
            font=font_body(),
            corner_radius=RADIUS_BUTTON,
            fg_color=colors["surface_elevated"],
            text_color=colors["text_primary"],
            hover_color=colors["card_hover"],
            command=self._cancel_upload
        )

        self._update_ui_mode()

    def _on_type_changed(self, value: str) -> None:
        self.media_type = value.upper()
        self._update_ui_mode()

    def _update_ui_mode(self) -> None:
        if not _HAS_CTK:
            return

        is_story = (self.media_type == "STORY")
        is_reel = (self.media_type == "REEL")

        # Story has no caption box
        if is_story:
            self._caption_container.pack_forget()
            self._reel_hint_lbl.pack_forget()
            self._share_btn.configure(text="Share Story")
        elif is_reel:
            self._caption_container.pack(fill="x", padx=12, pady=(0, 8))
            self._reel_hint_lbl.pack(fill="x", padx=12, pady=(0, 6), before=self._caption_container)
            self._share_btn.configure(text="Share Reel")
        else:
            self._caption_container.pack(fill="x", padx=12, pady=(0, 8))
            self._reel_hint_lbl.pack_forget()
            self._share_btn.configure(text="Share Post")

    def _choose_file(self) -> None:
        if not _HAS_CTK or not filedialog:
            return

        if self.media_type == "REEL":
            filetypes = [("MP4 Video", "*.mp4")]
        else:
            filetypes = [
                ("Media Files", "*.jpg *.jpeg *.png *.mp4"),
                ("Images", "*.jpg *.jpeg *.png"),
                ("Videos", "*.mp4")
            ]

        chosen = filedialog.askopenfilename(
            title=f"Select {self.media_type.capitalize()} Media",
            filetypes=filetypes
        )
        if chosen:
            self._handle_file_selected(chosen)

    def _handle_file_selected(self, filepath: str) -> None:
        p = Path(filepath)
        if not p.exists() or not p.is_file():
            Toast.show(self.winfo_toplevel(), "Selected file does not exist.", toast_type="error")
            return

        ext = p.suffix.lower()
        self.file_size = p.stat().st_size

        # Validation rules
        if self.media_type == "REEL" and ext != ".mp4":
            Toast.show(self.winfo_toplevel(), "Reels must be MP4 video files.", toast_type="error")
            return

        mime, _ = mimetypes.guess_type(filepath)
        if not mime:
            if ext in (".jpg", ".jpeg"):
                mime = "image/jpeg"
            elif ext == ".png":
                mime = "image/png"
            elif ext == ".mp4":
                mime = "video/mp4"
            else:
                mime = "application/octet-stream"

        self.content_type = mime

        # Size limit validation
        is_video = (ext == ".mp4" or "video" in mime)
        if is_video and self.file_size > self.MAX_VIDEO_SIZE:
            Toast.show(self.winfo_toplevel(), "Video exceeds 100 MB limit.", toast_type="error")
            return
        elif not is_video and self.file_size > self.MAX_IMAGE_SIZE:
            Toast.show(self.winfo_toplevel(), "Image exceeds 10 MB limit.", toast_type="error")
            return

        self.selected_file_path = filepath
        self._update_preview(filepath, is_video)

    def _update_preview(self, filepath: str, is_video: bool) -> None:
        if not _HAS_CTK or not hasattr(self, "_preview_label"):
            return

        colors = get_theme_colors(self.mode)
        size_mb = self.file_size / (1024 * 1024)
        filename = Path(filepath).name

        if is_video:
            self._preview_label.configure(
                text=f"🎬 Video Selected\n\n{filename}\nSize: {size_mb:.2f} MB\nFormat: MP4",
                image="",
                text_color=colors["text_primary"]
            )
        else:
            try:
                pil_img = Image.open(filepath)
                pil_img.thumbnail((320, 200))
                wrapped = wrap_image(pil_img, pil_img.size)
                self._preview_label.configure(text="", image=wrapped)
            except Exception as e:
                self._preview_label.configure(
                    text=f"📷 Image Selected\n\n{filename}\nSize: {size_mb:.2f} MB",
                    image="",
                    text_color=colors["text_primary"]
                )

    def _on_caption_changed(self) -> None:
        if not _HAS_CTK or not hasattr(self, "_caption_box"):
            return

        caption = self._caption_box.get("1.0", "end-1c")
        char_count = len(caption)
        colors = get_theme_colors(self.mode)

        self._char_counter.configure(
            text=f"{char_count} / {self.MAX_CAPTION_LEN}",
            text_color=colors["danger"] if char_count > self.MAX_CAPTION_LEN else colors["text_muted"]
        )

        # Extract hashtags
        tags = re.findall(r"#(\w+)", caption)
        self._render_hashtag_chips(tags)

    def _render_hashtag_chips(self, tags: List[str]) -> None:
        if not _HAS_CTK or not hasattr(self, "_tags_container"):
            return

        for child in self._tags_container.winfo_children():
            child.destroy()

        colors = get_theme_colors(self.mode)
        for tag in tags[:6]:
            chip = ctk.CTkLabel(
                self._tags_container,
                text=f"#{tag}",
                font=font_small(),
                text_color=colors["primary"],
                fg_color=colors["surface_elevated"],
                corner_radius=RADIUS_CHIP,
                height=22,
                padx=8
            )
            chip.pack(side="left", padx=2, pady=2)

    def _submit_upload(self) -> None:
        if self.is_uploading:
            return

        if not self.selected_file_path:
            Toast.show(self.winfo_toplevel(), "Please choose a media file first.", toast_type="error")
            return

        caption = self._caption_box.get("1.0", "end-1c").strip() if (self.media_type != "STORY" and _HAS_CTK) else ""
        if len(caption) > self.MAX_CAPTION_LEN:
            Toast.show(self.winfo_toplevel(), "Caption is too long.", toast_type="error")
            return

        api = self.app_state.api if self.app_state else None
        if not api:
            Toast.show(self.winfo_toplevel(), "API not available.", toast_type="error")
            return

        self.is_uploading = True
        self._cancel_requested = False
        self._set_uploading_ui(True)

        file_path = self.selected_file_path
        file_name = Path(file_path).name
        media_type = self.media_type
        content_type = self.content_type
        file_size = self.file_size

        def upload_flow_worker() -> Dict[str, Any]:
            # Step 1: Presign
            self._update_progress_main(0.05, "Step 1/3: Requesting upload permission...")
            presign_res = api.presign_upload(
                file_name=file_name,
                content_type=content_type,
                media_type=media_type,
                file_size=file_size
            )
            upload_url = presign_res.get("uploadUrl")
            r2_key = presign_res.get("r2Key")

            if self._cancel_requested:
                raise RuntimeError("Upload cancelled by user.")

            # Step 2: Binary stream PUT
            self._update_progress_main(0.15, "Step 2/3: Uploading binary payload...")

            def progress_cb(bytes_sent: int, total_bytes: int) -> None:
                if total_bytes > 0:
                    pct = bytes_sent / total_bytes
                    # Scale to 0.15 .. 0.85
                    scaled = 0.15 + (pct * 0.70)
                    self._update_progress_main(scaled, f"Uploading... {int(pct * 100)}%")

            api.upload_file_binary(
                upload_url=upload_url,
                file_path_or_bytes=file_path,
                content_type=content_type,
                progress_callback=progress_cb
            )

            if self._cancel_requested:
                raise RuntimeError("Upload cancelled by user.")

            # Step 3: Confirm
            self._update_progress_main(0.90, "Step 3/3: Confirming asset...")
            confirm_res = api.confirm_upload(
                r2_key=r2_key,
                media_type=media_type,
                caption=caption if caption else None
            )

            return confirm_res

        def on_success(card: Dict[str, Any]) -> None:
            self.is_uploading = False
            self._set_uploading_ui(False)
            Toast.show(self.winfo_toplevel(), "Posted successfully! 🎉", toast_type="success")
            self._reset_form()

            # Transition to target view
            if self.app_state and self.app_state.router:
                if media_type == "STORY":
                    self.app_state.router.switch_tab("Home")
                else:
                    self.app_state.router.switch_tab("Profile")

        def on_error(exc: Exception) -> None:
            self.is_uploading = False
            self._set_uploading_ui(False)
            logger.warning("Upload failed: %s", exc)
            Toast.show(self.winfo_toplevel(), f"Upload failed: {exc}", toast_type="error")

        run_async(upload_flow_worker, on_success=on_success, on_error=on_error)

    def _update_progress_main(self, fraction: float, message: str) -> None:
        if not _HAS_CTK:
            return
        try:
            self.after(0, lambda: self._apply_progress(fraction, message))
        except Exception:
            pass

    def _apply_progress(self, fraction: float, message: str) -> None:
        if not _HAS_CTK:
            return
        if hasattr(self, "_progress_bar"):
            self._progress_bar.set(fraction)
        if hasattr(self, "_status_label"):
            self._status_label.configure(text=message)

    def _cancel_upload(self) -> None:
        if self.is_uploading:
            self._cancel_requested = True
            Toast.show(self.winfo_toplevel(), "Cancelling upload...")

    def _set_uploading_ui(self, uploading: bool) -> None:
        if not _HAS_CTK:
            return

        if uploading:
            self._progress_bar.pack(fill="x", padx=20, pady=(4, 2), before=self._btn_row)
            self._status_label.pack(fill="x", padx=20, pady=(0, 6), before=self._btn_row)
            self._cancel_btn.pack(side="right", padx=(6, 0))
            self._share_btn.configure(state="disabled", text="Uploading...")
            self._choose_btn.configure(state="disabled")
            self._type_selector.configure(state="disabled")
        else:
            self._progress_bar.pack_forget()
            self._status_label.pack_forget()
            self._cancel_btn.pack_forget()
            self._share_btn.configure(state="normal", text=f"Share {self.media_type.capitalize()}")
            self._choose_btn.configure(state="normal")
            self._type_selector.configure(state="normal")

    def _reset_form(self) -> None:
        self.selected_file_path = None
        self.file_size = 0
        self.content_type = ""
        if not _HAS_CTK:
            return

        colors = get_theme_colors(self.mode)
        self._preview_label.configure(
            text="No media selected\n\nChoose an image or video to preview",
            image="",
            text_color=colors["text_muted"]
        )
        if hasattr(self, "_caption_box"):
            self._caption_box.delete("1.0", "end")
        if hasattr(self, "_char_counter"):
            self._char_counter.configure(text=f"0 / {self.MAX_CAPTION_LEN}")
        if hasattr(self, "_tags_container"):
            for child in self._tags_container.winfo_children():
                child.destroy()

    def on_enter(self, **kwargs: Any) -> None:
        initial_mode = kwargs.get("initial_mode")
        if initial_mode and initial_mode.upper() in ("POST", "REEL", "STORY"):
            self.media_type = initial_mode.upper()
            if _HAS_CTK and hasattr(self, "_type_selector"):
                self._type_selector.set(initial_mode.capitalize())
            self._update_ui_mode()

    def on_leave(self) -> None:
        pass
