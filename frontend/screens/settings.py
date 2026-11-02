"""
Settings Screen for SocialApp.
Provides appearance theme selector (Dark / Light / System) with persistence in config.json,
password update, privacy & notifications switches with backend persistence, disk cache
size calculator & purge button, and modal confirmation logout.

API Calls:
- PUT /api/auth/password {oldPassword, newPassword} -> 204
- PUT /api/users/me/settings {isPrivate, notificationsEnabled} -> {isPrivate, notificationsEnabled}
"""

import logging
from typing import Any, Callable, Dict, Optional

from ..async_utils import run_async
from ..cache import clear_disk_cache, get_disk_cache_size
from ..config import get_setting, set_setting
from ..theme import (
    get_theme_colors,
    font_body,
    font_caption,
    font_h2,
    RADIUS_BUTTON,
    RADIUS_CARD,
    RADIUS_ENTRY,
    style_danger_button,
    style_entry,
    style_primary_button,
)
from ..widgets import ConfirmDialog, Toast

logger = logging.getLogger("SocialApp.screens.settings")

_HAS_CTK = False
try:
    import customtkinter as ctk
    _HAS_CTK = True
except Exception:
    ctk = None
    _HAS_CTK = False

_FrameBase = ctk.CTkFrame if _HAS_CTK else object


class SettingsScreen(_FrameBase):
    """
    Settings screen for user preferences, security, storage cache, and session management.
    """

    def __init__(
        self,
        master: Any,
        app_state: Any = None,
        on_logout: Optional[Callable[[], None]] = None,
        mode: str = "dark",
        **kwargs: Any
    ) -> None:
        self.app_state = app_state
        self.on_logout = on_logout
        self.mode = mode

        self.is_private = False
        self.notifications_enabled = True

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
            text="Settings",
            font=font_h2(),
            text_color=colors["text_primary"]
        )
        title_lbl.pack(pady=(12, 6))

        # Scrollable Viewport
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True, padx=4, pady=0)

        # Section 1: Appearance Theme
        self._build_section_header("Appearance")
        theme_card = self._create_card_container()

        theme_lbl = ctk.CTkLabel(
            theme_card,
            text="Theme Mode",
            font=font_body(bold=True),
            text_color=colors["text_primary"]
        )
        theme_lbl.pack(side="left", padx=16, pady=12)

        cur_mode = get_setting("appearance_mode", "dark").capitalize()
        self._theme_selector = ctk.CTkSegmentedButton(
            theme_card,
            values=["Dark", "Light", "System"],
            command=self._on_theme_changed,
            font=font_caption(bold=True),
            fg_color=colors["surface_elevated"],
            selected_color=colors["primary"],
            selected_hover_color=colors["primary_hover"],
            corner_radius=RADIUS_BUTTON
        )
        self._theme_selector.set(cur_mode)
        self._theme_selector.pack(side="right", padx=12, pady=8)

        # Section 2: Privacy & Account
        self._build_section_header("Account & Privacy")
        privacy_card = self._create_card_container(is_horizontal=False)

        # Private Account Switch
        priv_row = ctk.CTkFrame(privacy_card, fg_color="transparent")
        priv_row.pack(fill="x", padx=16, pady=(12, 4))

        priv_lbl = ctk.CTkLabel(
            priv_row,
            text="Private Account",
            font=font_body(bold=True),
            text_color=colors["text_primary"]
        )
        priv_lbl.pack(side="left")

        self._priv_switch = ctk.CTkSwitch(
            priv_row,
            text="",
            command=self._on_settings_switch_changed,
            progress_color=colors["primary"],
            width=48
        )
        self._priv_switch.pack(side="right")

        priv_desc = ctk.CTkLabel(
            privacy_card,
            text="When your account is private, only people you approve can see your photos, reels, and stories.",
            font=font_caption(),
            text_color=colors["text_muted"],
            anchor="w",
            justify="left",
            wraplength=380
        )
        priv_desc.pack(fill="x", padx=16, pady=(0, 10))

        # Divider inside card
        div1 = ctk.CTkFrame(privacy_card, height=1, fg_color=colors["divider"])
        div1.pack(fill="x", padx=16, pady=4)

        # Push Notifications Switch
        notif_row = ctk.CTkFrame(privacy_card, fg_color="transparent")
        notif_row.pack(fill="x", padx=16, pady=(8, 12))

        notif_lbl = ctk.CTkLabel(
            notif_row,
            text="Push Notifications",
            font=font_body(bold=True),
            text_color=colors["text_primary"]
        )
        notif_lbl.pack(side="left")

        self._notif_switch = ctk.CTkSwitch(
            notif_row,
            text="",
            command=self._on_settings_switch_changed,
            progress_color=colors["primary"],
            width=48
        )
        self._notif_switch.pack(side="right")

        # Section 3: Password Security
        self._build_section_header("Security")
        sec_card = self._create_card_container(is_horizontal=False)

        sec_title = ctk.CTkLabel(
            sec_card,
            text="Change Password",
            font=font_body(bold=True),
            text_color=colors["text_primary"],
            anchor="w"
        )
        sec_title.pack(fill="x", padx=16, pady=(12, 6))

        self._old_pw_entry = ctk.CTkEntry(
            sec_card,
            placeholder_text="Current password",
            show="•",
            height=36,
            corner_radius=RADIUS_ENTRY,
            font=font_body()
        )
        style_entry(self._old_pw_entry, self.mode)
        self._old_pw_entry.pack(fill="x", padx=16, pady=4)

        self._new_pw_entry = ctk.CTkEntry(
            sec_card,
            placeholder_text="New password (min 8 chars, letter & digit)",
            show="•",
            height=36,
            corner_radius=RADIUS_ENTRY,
            font=font_body()
        )
        style_entry(self._new_pw_entry, self.mode)
        self._new_pw_entry.pack(fill="x", padx=16, pady=4)

        self._confirm_pw_entry = ctk.CTkEntry(
            sec_card,
            placeholder_text="Confirm new password",
            show="•",
            height=36,
            corner_radius=RADIUS_ENTRY,
            font=font_body()
        )
        style_entry(self._confirm_pw_entry, self.mode)
        self._confirm_pw_entry.pack(fill="x", padx=16, pady=4)

        update_pw_btn = ctk.CTkButton(
            sec_card,
            text="Update Password",
            font=font_caption(bold=True),
            height=34,
            corner_radius=RADIUS_BUTTON,
            command=self._submit_password_change
        )
        style_primary_button(update_pw_btn, self.mode)
        update_pw_btn.pack(fill="x", padx=16, pady=(8, 14))

        # Section 4: Storage & Cache
        self._build_section_header("Storage & Cache")
        cache_card = self._create_card_container()

        cache_info_frame = ctk.CTkFrame(cache_card, fg_color="transparent")
        cache_info_frame.pack(side="left", padx=16, pady=10)

        c_title = ctk.CTkLabel(
            cache_info_frame,
            text="Disk Image Cache",
            font=font_body(bold=True),
            text_color=colors["text_primary"],
            anchor="w"
        )
        c_title.pack(anchor="w")

        self._cache_size_lbl = ctk.CTkLabel(
            cache_info_frame,
            text="Calculating…",
            font=font_caption(),
            text_color=colors["text_muted"],
            anchor="w"
        )
        self._cache_size_lbl.pack(anchor="w")

        clear_cache_btn = ctk.CTkButton(
            cache_card,
            text="Clear Cache",
            font=font_caption(bold=True),
            width=90,
            height=32,
            corner_radius=RADIUS_BUTTON,
            fg_color=colors["surface_elevated"],
            text_color=colors["text_primary"],
            hover_color=colors["card_hover"],
            command=self._on_clear_cache_clicked
        )
        clear_cache_btn.pack(side="right", padx=14, pady=10)

        # Section 5: Logout Action
        logout_btn = ctk.CTkButton(
            self._scroll,
            text="Log Out",
            font=font_body(bold=True),
            height=40,
            corner_radius=RADIUS_BUTTON,
            command=self._confirm_logout
        )
        style_danger_button(logout_btn, self.mode)
        logout_btn.pack(fill="x", padx=12, pady=(20, 24))

        self._update_cache_display()

    def _build_section_header(self, title: str) -> None:
        if not _HAS_CTK:
            return
        colors = get_theme_colors(self.mode)
        lbl = ctk.CTkLabel(
            self._scroll,
            text=title,
            font=font_caption(bold=True),
            text_color=colors["text_secondary"],
            anchor="w"
        )
        lbl.pack(fill="x", padx=14, pady=(12, 4))

    def _create_card_container(self, is_horizontal: bool = True) -> Any:
        colors = get_theme_colors(self.mode)
        card = ctk.CTkFrame(
            self._scroll,
            fg_color=colors["surface"],
            corner_radius=RADIUS_CARD,
            border_width=1,
            border_color=colors["border"]
        )
        card.pack(fill="x", padx=12, pady=(0, 6))
        return card

    def _on_theme_changed(self, value: str) -> None:
        new_mode = value.lower()
        set_setting("appearance_mode", new_mode)
        if self.app_state:
            self.app_state.mode = new_mode

        if _HAS_CTK:
            ctk.set_appearance_mode(new_mode)
            Toast.show(self.winfo_toplevel(), f"Theme set to {value}", toast_type="success")

    def _on_settings_switch_changed(self) -> None:
        if not _HAS_CTK:
            return

        is_priv = bool(self._priv_switch.get())
        notif_en = bool(self._notif_switch.get())
        api = self.app_state.api if self.app_state else None
        if not api:
            return

        def worker() -> Dict[str, Any]:
            return api.update_settings(is_private=is_priv, notifications_enabled=notif_en)

        def on_success(res: Dict[str, Any]) -> None:
            self.is_private = res.get("isPrivate", is_priv)
            self.notifications_enabled = res.get("notificationsEnabled", notif_en)
            if self.app_state and self.app_state.current_user:
                self.app_state.current_user["isPrivate"] = self.is_private
                self.app_state.current_user["notificationsEnabled"] = self.notifications_enabled
            Toast.show(self.winfo_toplevel(), "Settings updated.", toast_type="success")

        def on_error(exc: Exception) -> None:
            logger.warning("Failed to update settings: %s", exc)
            Toast.show(self.winfo_toplevel(), f"Update failed: {exc}", toast_type="error")

        run_async(worker, on_success=on_success, on_error=on_error)

    def _submit_password_change(self) -> None:
        if not _HAS_CTK:
            return

        old_pw = self._old_pw_entry.get().strip()
        new_pw = self._new_pw_entry.get().strip()
        confirm_pw = self._confirm_pw_entry.get().strip()

        if not old_pw:
            Toast.show(self.winfo_toplevel(), "Please enter current password.", toast_type="error")
            return
        if len(new_pw) < 8:
            Toast.show(self.winfo_toplevel(), "New password must be at least 8 characters.", toast_type="error")
            return
        if new_pw != confirm_pw:
            Toast.show(self.winfo_toplevel(), "New passwords do not match.", toast_type="error")
            return

        api = self.app_state.api if self.app_state else None
        if not api:
            return

        def worker() -> None:
            api.change_password(old_password=old_pw, new_password=new_pw)

        def on_success(_: Any) -> None:
            self._old_pw_entry.delete(0, "end")
            self._new_pw_entry.delete(0, "end")
            self._confirm_pw_entry.delete(0, "end")
            Toast.show(self.winfo_toplevel(), "Password updated successfully!", toast_type="success")

        def on_error(exc: Exception) -> None:
            Toast.show(self.winfo_toplevel(), f"Password update failed: {exc}", toast_type="error")

        run_async(worker, on_success=on_success, on_error=on_error)

    def _update_cache_display(self) -> None:
        if not _HAS_CTK or not hasattr(self, "_cache_size_lbl"):
            return
        total_bytes = get_disk_cache_size()
        mb = total_bytes / (1024 * 1024)
        self._cache_size_lbl.configure(text=f"{mb:.2f} MB cached on disk")

    def _on_clear_cache_clicked(self) -> None:
        clear_disk_cache()
        self._update_cache_display()
        if _HAS_CTK:
            Toast.show(self.winfo_toplevel(), "Disk cache cleared.", toast_type="success")

    def _confirm_logout(self) -> None:
        if not _HAS_CTK:
            return

        ConfirmDialog(
            self.winfo_toplevel(),
            title="Log Out",
            message="Are you sure you want to log out of SocialApp?",
            confirm_text="Log Out",
            is_danger=True,
            on_confirm=self._execute_logout
        )

    def _execute_logout(self) -> None:
        logger.info("Executing user logout.")
        if self.app_state:
            # Stop playback
            if self.app_state.player:
                try:
                    self.app_state.player.stop()
                except Exception:
                    pass
            # Clear credentials
            if self.app_state.api:
                self.app_state.api.clear_token()
            self.app_state.current_user = None

        if self.on_logout:
            self.on_logout()
        elif self.app_state and self.app_state.router:
            # Switch to Login screen
            from .login import LoginScreen
            self.app_state.router.switch_tab("Login")

    def on_enter(self, **kwargs: Any) -> None:
        self._update_cache_display()
        if self.app_state and self.app_state.current_user:
            u = self.app_state.current_user
            self.is_private = bool(u.get("isPrivate", False))
            self.notifications_enabled = bool(u.get("notificationsEnabled", True))
            if _HAS_CTK:
                if hasattr(self, "_priv_switch"):
                    if self.is_private:
                        self._priv_switch.select()
                    else:
                        self._priv_switch.deselect()
                if hasattr(self, "_notif_switch"):
                    if self.notifications_enabled:
                        self._notif_switch.select()
                    else:
                        self._notif_switch.deselect()

    def on_leave(self) -> None:
        pass
