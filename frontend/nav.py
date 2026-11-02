"""
Stack-based Navigation Router for SocialApp.
Coordinates view transitions, tab switching, nested view push/pop history,
top-bar Back button visibility, and on_enter / on_leave lifecycle hooks (such as player release).
"""

import inspect
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union

logger = logging.getLogger("SocialApp.nav")

try:
    from .anim import slide_in
except Exception:  # pragma: no cover
    slide_in = None


def _show_view(view: Any, animate_in: bool = False) -> None:
    """Show a view filling its container (place-based so it can slide in)."""
    try:
        if hasattr(view, "place") and hasattr(view, "winfo_id"):
            view.place(x=0, y=0, relwidth=1.0, relheight=1.0)
            if animate_in and slide_in is not None:
                slide_in(view)
        else:
            view.pack(fill="both", expand=True)
        if hasattr(view, "tkraise"):
            view.tkraise()
    except Exception:
        pass


def _hide_view(view: Any) -> None:
    """Hide a view regardless of the geometry manager that showed it."""
    for fn in ("place_forget", "pack_forget"):
        try:
            getattr(view, fn)()
        except Exception:
            pass


class NavigationRouter:
    """
    Manages navigation stacks, tab states, and screen lifecycles.
    """

    def __init__(
        self,
        container_frame: Any = None,
        player: Any = None,
        top_bar: Any = None,
        bottom_nav: Any = None
    ) -> None:
        self._container = container_frame
        self._player = player
        self._top_bar = top_bar
        self._bottom_nav = bottom_nav

        # Tab registry: {tab_name: (screen_factory_or_class, kwargs)}
        self._tabs: Dict[str, Tuple[Any, Dict[str, Any]]] = {}
        # Tab instance cache: {tab_name: screen_instance}
        self._tab_instances: Dict[str, Any] = {}
        self._active_tab: Optional[str] = None

        # View stack: list of (view_instance, title, is_tab_root)
        self._stack: List[Tuple[Any, str, bool]] = []

    def set_container(self, container_frame: Any) -> None:
        self._container = container_frame

    def set_player(self, player: Any) -> None:
        self._player = player

    def set_top_bar(self, top_bar: Any) -> None:
        self._top_bar = top_bar

    def set_bottom_nav(self, bottom_nav: Any) -> None:
        self._bottom_nav = bottom_nav

    def register_tab(self, tab_name: str, factory_or_class: Any, **kwargs: Any) -> None:
        """Register a primary navigation tab factory or view class."""
        self._tabs[tab_name] = (factory_or_class, kwargs)

    def get_current_view(self) -> Optional[Any]:
        """Return the currently displayed screen/view instance."""
        if self._stack:
            return self._stack[-1][0]
        return None

    def can_pop(self) -> bool:
        """Return True if there is a nested screen that can be popped."""
        return len(self._stack) > 1

    def _call_on_leave(self, view: Any) -> None:
        """Invoke on_leave lifecycle hook on outgoing view and ensure player is stopped."""
        if view is not None:
            if hasattr(view, "on_leave"):
                try:
                    view.on_leave()
                except Exception as e:
                    logger.warning("Error in %s.on_leave(): %s", type(view).__name__, e)

        # Stop shared player on view transitions to prevent rogue audio/video
        if self._player:
            try:
                self._player.stop()
            except Exception:
                pass

    def _call_on_enter(self, view: Any, **kwargs: Any) -> None:
        """Invoke on_enter lifecycle hook on incoming view."""
        if view is not None and hasattr(view, "on_enter"):
            try:
                view.on_enter(**kwargs)
            except Exception as e:
                logger.warning("Error in %s.on_enter(): %s", type(view).__name__, e)

    def _update_chrome(self) -> None:
        """Update top-bar back button visibility and title according to stack state."""
        has_back = self.can_pop()
        current_title = self._stack[-1][1] if self._stack else "SocialApp"

        if self._top_bar is not None:
            if hasattr(self._top_bar, "set_back_button_visible"):
                self._top_bar.set_back_button_visible(has_back)
            if hasattr(self._top_bar, "set_title"):
                self._top_bar.set_title(current_title)

        if self._bottom_nav is not None and self._active_tab:
            if hasattr(self._bottom_nav, "set_active_tab"):
                self._bottom_nav.set_active_tab(self._active_tab)

    def set_chrome_visible(self, visible: bool) -> None:
        """Show or hide top bar and bottom navigation bar (e.g. during authentication)."""
        if self._top_bar is not None and hasattr(self._top_bar, "set_visible"):
            self._top_bar.set_visible(visible)
        if self._bottom_nav is not None and hasattr(self._bottom_nav, "set_visible"):
            self._bottom_nav.set_visible(visible)

    def pop_to_root(self) -> None:
        """Pop all nested views until reaching the tab root view."""
        while self.can_pop():
            self.pop()

    def switch_tab(self, tab_name: str, **kwargs: Any) -> None:
        """
        Switch primary bottom navigation tab.
        Clears the sub-view stack, hides outgoing view, and displays the tab root view.
        """
        if tab_name not in self._tabs:
            logger.warning("Tab '%s' is not registered.", tab_name)
            return

        # Leave current view
        current_view = self.get_current_view()
        if current_view is not None:
            self._call_on_leave(current_view)
            _hide_view(current_view)

        # Clear stack
        for view, _, is_root in reversed(self._stack):
            if not is_root:
                try:
                    view.destroy()
                except Exception:
                    pass
        self._stack.clear()

        # Instantiate or retrieve tab instance
        if tab_name not in self._tab_instances:
            factory, default_kwargs = self._tabs[tab_name]
            merged_kwargs = {**default_kwargs, **kwargs}
            if self._container is not None:
                instance = factory(self._container, **merged_kwargs)
            else:
                instance = factory(**merged_kwargs)
            self._tab_instances[tab_name] = instance

        tab_view = self._tab_instances[tab_name]
        self._active_tab = tab_name
        self._stack.append((tab_view, tab_name, True))

        # Show tab view
        _show_view(tab_view, animate_in=True)

        self._call_on_enter(tab_view, **kwargs)
        if tab_name == "Login":
            self.set_chrome_visible(False)
        else:
            self.set_chrome_visible(True)
        self._update_chrome()

    def push(self, view_or_class: Any, title: str = "", **kwargs: Any) -> Any:
        """
        Push a new screen onto the navigation stack (e.g. Profile, Comments, Detail).
        Hides current view and shows pushed view.
        """
        current_view = self.get_current_view()
        if current_view is not None:
            self._call_on_leave(current_view)
            _hide_view(current_view)

        # Instantiate if class/factory passed
        # NOTE: a widget *class* also has "winfo_id" (as an unbound method), so classes
        # must be detected explicitly or they would be pushed uninstantiated.
        if inspect.isclass(view_or_class) or (callable(view_or_class) and not hasattr(view_or_class, "winfo_id")):
            if self._container is not None:
                view_instance = view_or_class(self._container, **kwargs)
            else:
                view_instance = view_or_class(**kwargs)
        else:
            view_instance = view_or_class

        self._stack.append((view_instance, title or type(view_instance).__name__, False))

        _show_view(view_instance, animate_in=True)

        self._call_on_enter(view_instance, **kwargs)
        self._update_chrome()
        return view_instance

    def pop(self) -> Optional[Any]:
        """
        Pop the top view from stack and restore the previous screen.
        """
        if not self.can_pop():
            return None

        popped_view, _, is_root = self._stack.pop()
        self._call_on_leave(popped_view)

        _hide_view(popped_view)
        try:
            if not is_root:
                popped_view.destroy()
        except Exception:
            pass

        restored_view, _, _ = self._stack[-1]
        _show_view(restored_view, animate_in=False)

        self._call_on_enter(restored_view)
        self._update_chrome()
        return popped_view
