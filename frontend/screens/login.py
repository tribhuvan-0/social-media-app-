"""
Login and Signup screen for SocialApp.
Manages credential entry, client-side validation, async authentication dispatch,
session saving in AppState, and transition to Home feed.

API Calls:
- POST /api/auth/login {username, password} -> {token, user: Me}
- POST /api/auth/signup {username, email, password} -> 201 {token, user: Me}
"""

import logging
import re
from typing import Any, Callable, Dict, Optional

from ..async_utils import run_async
from ..theme import (
    get_theme_colors,
    font_logo,
    font_h1,
    font_h2,
    font_body,
    font_caption,
    font_small,
    RADIUS_CARD,
    RADIUS_BUTTON,
    RADIUS_ENTRY,
    style_primary_button,
    style_entry,
)
from ..widgets import Toast

logger = logging.getLogger("SocialApp.screens.login")

_HAS_CTK = False
try:
    import customtkinter as ctk
    _HAS_CTK = True
except Exception:
    ctk = None
    _HAS_CTK = False

_FrameBase = ctk.CTkFrame if _HAS_CTK else object


class LoginScreen(_FrameBase):
    """
    Login & Signup view with tab switching, inline validation, and async auth calls.
    """

    def __init__(
        self,
        master: Any,
        app_state: Any = None,
        on_login_success: Optional[Callable[[Dict[str, Any]], None]] = None,
        mode: str = "dark",
        **kwargs: Any
    ) -> None:
        self.app_state = app_state
        self.on_login_success = on_login_success
        self.mode = mode
        self.is_signup = False
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

        # Centered container frame
        self._container = ctk.CTkFrame(
            self,
            width=380,
            fg_color=colors["surface"],
            corner_radius=RADIUS_CARD,
            border_width=1,
            border_color=colors["border"]
        )
        self._container.place(relx=0.5, rely=0.5, anchor="center")

        # Top padding & Brand logo
        self._logo_label = ctk.CTkLabel(
            self._container,
            text="SocialApp",
            font=font_logo(),
            text_color=colors["text_primary"]
        )
        self._logo_label.pack(pady=(28, 4))

        self._subtitle_label = ctk.CTkLabel(
            self._container,
            text="Sign in to connect with friends & share media.",
            font=font_caption(),
            text_color=colors["text_muted"],
            wraplength=320
        )
        self._subtitle_label.pack(pady=(0, 20))

        # Mode Tab Selector (Log In / Sign Up)
        self._tab_selector = ctk.CTkSegmentedButton(
            self._container,
            values=["Log In", "Sign Up"],
            command=self._on_tab_changed,
            font=font_body(bold=True),
            fg_color=colors["surface_elevated"],
            selected_color=colors["primary"],
            selected_hover_color=colors["primary_hover"],
            unselected_color=colors["surface_elevated"],
            unselected_hover_color=colors["card_hover"],
            corner_radius=RADIUS_BUTTON
        )
        self._tab_selector.set("Log In")
        self._tab_selector.pack(fill="x", padx=30, pady=(0, 16))

        # Error display label
        self._error_label = ctk.CTkLabel(
            self._container,
            text="",
            font=font_caption(bold=True),
            text_color=colors["danger"],
            wraplength=320
        )
        self._error_label.pack(pady=(0, 8))

        # Form fields container
        self._form_frame = ctk.CTkFrame(self._container, fg_color="transparent")
        self._form_frame.pack(fill="x", padx=30)

        # 1. Username
        self._username_entry = ctk.CTkEntry(
            self._form_frame,
            placeholder_text="Username",
            height=40,
            corner_radius=RADIUS_ENTRY,
            font=font_body()
        )
        style_entry(self._username_entry, self.mode)
        self._username_entry.pack(fill="x", pady=6)
        self._username_entry.bind("<Return>", lambda e: self._submit())

        # 2. Email (Signup only)
        self._email_entry = ctk.CTkEntry(
            self._form_frame,
            placeholder_text="Email address",
            height=40,
            corner_radius=RADIUS_ENTRY,
            font=font_body()
        )
        style_entry(self._email_entry, self.mode)

        # 3. Password
        self._password_entry = ctk.CTkEntry(
            self._form_frame,
            placeholder_text="Password",
            show="•",
            height=40,
            corner_radius=RADIUS_ENTRY,
            font=font_body()
        )
        style_entry(self._password_entry, self.mode)
        self._password_entry.pack(fill="x", pady=6)
        self._password_entry.bind("<Return>", lambda e: self._submit())

        # 4. Confirm Password (Signup only)
        self._confirm_password_entry = ctk.CTkEntry(
            self._form_frame,
            placeholder_text="Confirm password",
            show="•",
            height=40,
            corner_radius=RADIUS_ENTRY,
            font=font_body()
        )
        style_entry(self._confirm_password_entry, self.mode)
        self._confirm_password_entry.bind("<Return>", lambda e: self._submit())

        # Submit button
        self._submit_btn = ctk.CTkButton(
            self._container,
            text="Log In",
            height=42,
            font=font_body(bold=True),
            corner_radius=RADIUS_BUTTON,
            command=self._submit
        )
        style_primary_button(self._submit_btn, self.mode)
        self._submit_btn.pack(fill="x", padx=30, pady=(16, 12))

        # Demo mode fast fill button (convenience for evaluation)
        self._demo_btn = ctk.CTkButton(
            self._container,
            text="Use Demo Account (elena_v)",
            height=30,
            font=font_small(),
            fg_color="transparent",
            text_color=colors["text_muted"],
            hover_color=colors["surface_elevated"],
            command=self._fill_demo_credentials
        )
        self._demo_btn.pack(pady=(0, 20))

    def _fill_demo_credentials(self) -> None:
        """Fill standard credentials for fast testing."""
        if not _HAS_CTK:
            return
        self._tab_selector.set("Log In")
        self._on_tab_changed("Log In")
        demo_user = "testuser" if (self.app_state and getattr(self.app_state, "use_mock", False)) else "elena_v"
        self._username_entry.delete(0, "end")
        self._username_entry.insert(0, demo_user)
        self._password_entry.delete(0, "end")
        self._password_entry.insert(0, "Password123")
        self._clear_error()

    def _on_tab_changed(self, value: str) -> None:
        self.is_signup = (value == "Sign Up")
        self._clear_error()

        if not _HAS_CTK:
            return

        if self.is_signup:
            self._email_entry.pack(after=self._username_entry, fill="x", pady=6)
            self._confirm_password_entry.pack(after=self._password_entry, fill="x", pady=6)
            self._submit_btn.configure(text="Sign Up")
        else:
            self._email_entry.pack_forget()
            self._confirm_password_entry.pack_forget()
            self._submit_btn.configure(text="Log In")

    def _show_error(self, message: str) -> None:
        if _HAS_CTK and hasattr(self, "_error_label"):
            self._error_label.configure(text=message)

    def _clear_error(self) -> None:
        if _HAS_CTK and hasattr(self, "_error_label"):
            self._error_label.configure(text="")

    def validate_inputs(
        self,
        username: str,
        password: str,
        email: str = "",
        confirm_password: str = ""
    ) -> Optional[str]:
        """
        Validate inputs against client-side specification.
        Returns error string if invalid, None if valid.
        """
        if not username:
            return "Username is required."
        if not re.match(r"^[a-zA-Z0-9_]{3,30}$", username):
            return "Username must be 3-30 characters (letters, numbers, _)."

        if self.is_signup:
            if not email:
                return "Email address is required."
            if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
                return "Please enter a valid email address."

        if not password:
            return "Password is required."
        if len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
            return "Password must be at least 8 chars with 1 letter & 1 digit."

        if self.is_signup and password != confirm_password:
            return "Passwords do not match."

        return None

    def _submit(self) -> None:
        if self.is_loading:
            return

        username = self._username_entry.get().strip() if _HAS_CTK else ""
        password = self._password_entry.get().strip() if _HAS_CTK else ""
        email = self._email_entry.get().strip() if (self.is_signup and _HAS_CTK) else ""
        confirm = self._confirm_password_entry.get().strip() if (self.is_signup and _HAS_CTK) else ""

        error = self.validate_inputs(username, password, email, confirm)
        if error:
            self._show_error(error)
            return

        self._clear_error()
        self._set_loading(True)

        api = self.app_state.api if self.app_state else None
        if not api:
            self._show_error("API client not available.")
            self._set_loading(False)
            return

        is_signup = self.is_signup

        def worker_call() -> Dict[str, Any]:
            if is_signup:
                return api.signup(username=username, email=email, password=password)
            else:
                return api.login(username=username, password=password)

        def on_success(res: Dict[str, Any]) -> None:
            self._set_loading(False)
            user_info = res.get("user")
            token = res.get("token")

            if self.app_state:
                if token:
                    self.app_state.api.set_token(token)
                self.app_state.current_user = user_info

            if self.on_login_success:
                self.on_login_success(res)
            elif self.app_state and self.app_state.router:
                self.app_state.router.switch_tab("Home")

        def on_error(exc: Exception) -> None:
            self._set_loading(False)
            err_msg = str(exc)
            if hasattr(exc, "message") and exc.message:
                err_msg = exc.message
            self._show_error(err_msg)

        run_async(worker_call, on_success=on_success, on_error=on_error)

    def _set_loading(self, loading: bool) -> None:
        self.is_loading = loading
        if not _HAS_CTK:
            return
        if loading:
            self._submit_btn.configure(
                text="Creating account..." if self.is_signup else "Logging in...",
                state="disabled"
            )
        else:
            self._submit_btn.configure(
                text="Sign Up" if self.is_signup else "Log In",
                state="normal"
            )

    def on_enter(self, **kwargs: Any) -> None:
        self._clear_error()
        self._set_loading(False)

    def on_leave(self) -> None:
        self._clear_error()
