"""
Main application entry point for the SocialApp desktop client.
Configures 480x860 fixed mobile window, TopBar, BottomNav, NavigationRouter,
AppState container, 40ms async queue pump, and graceful exit cleanup.
"""

import logging
import os
import sys
from typing import Any, Dict, Optional

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    __package__ = "frontend"

from .async_utils import shutdown_async, start_queue_pump, stop_queue_pump
from .config import (
    API_BASE_URL,
    USE_MOCK,
    WINDOW_HEIGHT,
    WINDOW_TITLE,
    WINDOW_WIDTH,
    get_setting,
    is_backend_reachable,
    load_config,
    set_setting,
)
from .nav import NavigationRouter
from .player import get_shared_player
from .theme import (
    get_color,
    get_theme_colors,
    font_logo,
    font_body,
    font_h2,
    font_caption,
    RADIUS_BUTTON,
)
from .api import ApiClient
from .mock_api import MockApi
from .widgets import Toast
from .screens import (
    LoginScreen,
    HomeScreen,
    StoriesScreen,
    StoriesViewerModal,
    ReelsScreen,
    ExploreScreen,
    CreateScreen,
    ProfileScreen,
    MessagesScreen,
    ActivityScreen,
    SettingsScreen,
    CommentsModal,
    FollowListModal,
)

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
from .theme import UI_FONT
from .anim import install_smooth_hover, pop_button

logger = logging.getLogger("SocialApp.main")

# Detect CustomTkinter
_HAS_CTK = False
try:
    import customtkinter as ctk
    _HAS_CTK = True
except Exception:
    ctk = None
    _HAS_CTK = False


class AppState:
    """Central container for application-wide dependencies and state."""

    def __init__(self) -> None:
        self.config = load_config()
        self.mode = self.config.get("appearance_mode", "dark")
        self.use_mock = USE_MOCK or not is_backend_reachable()

        if self.use_mock:
            logger.info("Initializing MockApi for offline / demo mode.")
            self.api = MockApi()
        else:
            logger.info("Initializing ApiClient connecting to %s.", API_BASE_URL)
            self.api = ApiClient(base_url=API_BASE_URL)

        self.player = get_shared_player()
        self.api.set_player(self.player)
        self.current_user: Optional[Dict[str, Any]] = None

        if self.use_mock:
            try:
                self.current_user = self.api.get_me()
            except Exception:
                self.current_user = None

        self.router: Optional[NavigationRouter] = None


class TopBar:
    """Top bar component managing logo, back button, and auxiliary icons."""

    def __init__(
        self,
        master: Any,
        router: NavigationRouter,
        mode: str = "dark",
        on_activity_click: Optional[Any] = None,
        on_messages_click: Optional[Any] = None
    ) -> None:
        self._router = router
        self._mode = mode
        colors = get_theme_colors(mode)

        if _HAS_CTK and master is not None:
            self._frame = ctk.CTkFrame(
                master,
                height=52,
                corner_radius=0,
                fg_color=colors["bg"],
                border_width=0
            )
            self._frame.pack(fill="x", side="top")
            self._frame.pack_propagate(False)

            # Left side: Back Button & Title
            left_frame = ctk.CTkFrame(self._frame, fg_color="transparent")
            left_frame.pack(side="left", padx=12, fill="y")

            self._back_btn = ctk.CTkButton(
                left_frame,
                text="←",
                width=32,
                height=32,
                font=(UI_FONT, 18, "bold"),
                fg_color="transparent",
                hover_color=colors["surface_elevated"],
                text_color=colors["text_primary"],
                command=self._on_back_clicked
            )

            self._title_label = ctk.CTkLabel(
                left_frame,
                text=WINDOW_TITLE,
                font=font_logo(),
                text_color=colors["text_primary"]
            )
            self._title_label.pack(side="left", padx=(0, 4))

            # Right side icons: Activity (Heart) & Direct Messages (Paperplane)
            right_frame = ctk.CTkFrame(self._frame, fg_color="transparent")
            right_frame.pack(side="right", padx=12, fill="y")

            self._heart_btn = ctk.CTkButton(
                right_frame,
                text="♡",
                width=34,
                height=34,
                font=(UI_FONT, 18),
                fg_color="transparent",
                hover_color=colors["surface_elevated"],
                text_color=colors["text_primary"],
                command=on_activity_click
            )
            self._heart_btn.pack(side="left", padx=2)

            self._msg_btn = ctk.CTkButton(
                right_frame,
                text="✉",
                width=34,
                height=34,
                font=(UI_FONT, 16),
                fg_color="transparent",
                hover_color=colors["surface_elevated"],
                text_color=colors["text_primary"],
                command=on_messages_click
            )
            self._msg_btn.pack(side="left", padx=2)

            # Bottom separator line
            divider = ctk.CTkFrame(self._frame, height=1, fg_color=colors["divider"])
            divider.place(relx=0, rely=1.0, relwidth=1.0, anchor="sw")
        else:
            self._frame = None

    def _on_back_clicked(self) -> None:
        if self._router:
            self._router.pop()

    def set_back_button_visible(self, visible: bool) -> None:
        if not _HAS_CTK or not self._frame:
            return
        if visible:
            self._back_btn.pack(side="left", padx=(0, 6))
        else:
            self._back_btn.pack_forget()

    def set_title(self, title: str) -> None:
        if not _HAS_CTK or not self._frame:
            return
        display_title = title if title and title != "Home" else WINDOW_TITLE
        self._title_label.configure(text=display_title)

    def set_visible(self, visible: bool) -> None:
        if not _HAS_CTK or not self._frame:
            return
        if visible:
            self._frame.pack(fill="x", side="top")
        else:
            self._frame.pack_forget()


class BottomNavBar:
    """Bottom navigation bar with 5 primary icons: Home, Explore, Create, Reels, Profile."""

    TABS = [
        ("Home", "🏠"),
        ("Explore", "🔍"),
        ("Create", "⊞"),
        ("Reels", "🎬"),
        ("Profile", "👤"),
    ]

    def __init__(self, master: Any, router: NavigationRouter, mode: str = "dark") -> None:
        self._router = router
        self._mode = mode
        self._buttons: Dict[str, Any] = {}
        colors = get_theme_colors(mode)

        if _HAS_CTK and master is not None:
            self._frame = ctk.CTkFrame(
                master,
                height=56,
                corner_radius=0,
                fg_color=colors["bg"],
                border_width=0
            )
            self._frame.pack(fill="x", side="bottom")
            self._frame.pack_propagate(False)

            # Top separator line
            divider = ctk.CTkFrame(self._frame, height=1, fg_color=colors["divider"])
            divider.place(relx=0, rely=0, relwidth=1.0, anchor="nw")

            # 5 evenly-spaced action buttons
            button_width = WINDOW_WIDTH // len(self.TABS)
            for tab_name, icon in self.TABS:
                btn = ctk.CTkButton(
                    self._frame,
                    text=icon,
                    width=button_width - 12,
                    height=44,
                    corner_radius=22,
                    font=(UI_FONT, 18),
                    fg_color="transparent",
                    hover_color=colors["surface_elevated"],
                    text_color=colors["text_muted"],
                    command=lambda name=tab_name: self._router.switch_tab(name)
                )
                btn.pack(side="left", expand=True, padx=4, pady=6)
                self._buttons[tab_name] = btn
        else:
            self._frame = None

    def set_visible(self, visible: bool) -> None:
        if not _HAS_CTK or not self._frame:
            return
        if visible:
            self._frame.pack(fill="x", side="bottom")
        else:
            self._frame.pack_forget()

    def set_active_tab(self, active_tab: str) -> None:
        if not _HAS_CTK or not self._frame:
            return
        colors = get_theme_colors(self._mode)
        for tab_name, btn in self._buttons.items():
            if tab_name == active_tab:
                btn.configure(
                    text_color=colors["text_primary"],
                    fg_color=colors["surface_elevated"]
                )
                pop_button(btn, 18, UI_FONT, peak=1.25, duration_ms=220)
            else:
                btn.configure(
                    text_color=colors["text_muted"],
                    fg_color="transparent"
                )





def center_window(root: Any, width: int = WINDOW_WIDTH, height: int = WINDOW_HEIGHT) -> None:
    """Center window on the screen."""
    if not root:
        return
    try:
        root.update_idletasks()
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        x = max(0, (sw - width) // 2)
        y = max(0, (sh - height) // 2)
        root.geometry(f"{width}x{height}+{x}+{y}")
    except Exception:
        root.geometry(f"{width}x{height}")


class SocialApp:
    """Top-level SocialApp desktop client application."""

    def __init__(self) -> None:
        self.state = AppState()
        self.root: Optional[Any] = None
        self.router: Optional[NavigationRouter] = None

    def build_window(self) -> Any:
        if not _HAS_CTK:
            raise RuntimeError("CustomTkinter is not installed or GUI libraries are unavailable.")

        ctk.set_appearance_mode(self.state.mode)
        install_smooth_hover()
        self.root = ctk.CTk()
        self.root.title(WINDOW_TITLE)
        # Resizable on purpose: tiling compositors (Hyprland, sway...) float
        # fixed-size windows into a corner; a resizable window gets tiled/centered normally.
        self.root.resizable(True, True)
        self.root.minsize(420, 640)
        center_window(self.root, WINDOW_WIDTH, WINDOW_HEIGHT)
        self.root.configure(fg_color=get_theme_colors(self.state.mode)["bg"])

        # Centered phone-style column that follows the window size (max 560px wide)
        colors = get_theme_colors(self.state.mode)
        self.column = ctk.CTkFrame(
            self.root,
            width=WINDOW_WIDTH,
            fg_color=colors["bg"],
            border_width=1,
            border_color=colors["border"],
            corner_radius=18
        )
        self.column.place(relx=0.5, rely=0, anchor="n", relheight=1.0)
        self.column.pack_propagate(False)

        def _fit_column(event: Any = None) -> None:
            try:
                w = self.root.winfo_width()
                self.column.configure(width=max(420, min(560, w)))
            except Exception:
                pass

        self.root.bind("<Configure>", _fit_column, add="+")

        # Wire up player root
        if hasattr(self.state.player, "set_root"):
            self.state.player.set_root(self.root)

        # Content container
        colors = get_theme_colors(self.state.mode)
        self.content_container = ctk.CTkFrame(
            self.column,
            width=WINDOW_WIDTH,
            height=WINDOW_HEIGHT - 52 - 56,
            fg_color=colors["bg"],
            corner_radius=0
        )

        # Initialize NavigationRouter
        self.router = NavigationRouter(
            container_frame=self.content_container,
            player=self.state.player
        )
        self.state.router = self.router

        # Wire up session expired handler
        self.state.api.set_on_unauthorized(self.on_session_expired)

        # Top Bar & Bottom Nav
        self.top_bar = TopBar(
            self.column,
            self.router,
            mode=self.state.mode,
            on_activity_click=lambda: self.router.push(ActivityScreen, title="Notifications", app_state=self.state, mode=self.state.mode),
            on_messages_click=lambda: self.router.push(MessagesScreen, title="Messages", app_state=self.state, mode=self.state.mode)
        )
        self.bottom_nav = BottomNavBar(self.column, self.router, mode=self.state.mode)

        self.router.set_top_bar(self.top_bar)
        self.router.set_bottom_nav(self.bottom_nav)

        # Pack content container between top bar and bottom nav
        self.content_container.pack(fill="both", expand=True)

        # Register all application screens
        self.router.register_tab(
            "Login",
            lambda parent: LoginScreen(parent, app_state=self.state, on_login_success=self.on_login_success, mode=self.state.mode)
        )
        self.router.register_tab(
            "Home",
            lambda parent: HomeScreen(parent, app_state=self.state, mode=self.state.mode)
        )
        self.router.register_tab(
            "Explore",
            lambda parent: ExploreScreen(parent, app_state=self.state, mode=self.state.mode)
        )
        self.router.register_tab(
            "Create",
            lambda parent: CreateScreen(parent, app_state=self.state, mode=self.state.mode)
        )
        self.router.register_tab(
            "Reels",
            lambda parent: ReelsScreen(parent, app_state=self.state, mode=self.state.mode)
        )
        self.router.register_tab(
            "Profile",
            lambda parent: ProfileScreen(parent, app_state=self.state, mode=self.state.mode)
        )
        self.router.register_tab(
            "Activity",
            lambda parent: ActivityScreen(parent, app_state=self.state, mode=self.state.mode)
        )
        self.router.register_tab(
            "Messages",
            lambda parent: MessagesScreen(parent, app_state=self.state, mode=self.state.mode)
        )
        self.router.register_tab(
            "Settings",
            lambda parent: SettingsScreen(parent, app_state=self.state, on_logout=self.on_logout, mode=self.state.mode)
        )

        # Initial navigation state
        if self.state.current_user is not None:
            self.router.switch_tab("Home")
        else:
            self.router.switch_tab("Login")

        # Start 40ms main-thread queue pump
        start_queue_pump(self.root, interval_ms=40)

        # Intercept window close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        return self.root

    def on_login_success(self, res: Dict[str, Any]) -> None:
        """Invoked when user logs in or signs up successfully."""
        if self.router:
            self.router.set_chrome_visible(True)
            self.router.switch_tab("Home")

    def on_logout(self) -> None:
        """Invoked when user logs out."""
        if self.router:
            self.router.set_chrome_visible(False)
            self.router.switch_tab("Login")

    def on_session_expired(self) -> None:
        """Invoked when API returns 401 Unauthorized."""
        if self.root:
            Toast.show(self.root, "Session expired. Please log in again.", toast_type="error")
        self.on_logout()

    def on_close(self) -> None:
        """Graceful window close handler."""
        logger.info("Closing SocialApp...")
        # Stop player
        if self.state.player:
            try:
                self.state.player.stop()
                self.state.player.release()
            except Exception:
                pass

        # Stop queue pump
        if self.root:
            stop_queue_pump(self.root)

        # Shutdown worker pool
        shutdown_async(wait=False)

        # Destroy window
        if self.root:
            try:
                self.root.destroy()
            except Exception:
                pass


def main() -> None:
    """Application launcher."""
    app = SocialApp()
    if _HAS_CTK:
        root = app.build_window()
        root.mainloop()
    else:
        logger.warning(
            "CustomTkinter is not available in this environment. "
            "Desktop GUI cannot be rendered interactively."
        )


if __name__ == "__main__":
    main()
