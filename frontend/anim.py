"""
Lightweight animation engine for the SocialApp desktop client.

All animations are *time based* (not frame-count based) and tick every ~8 ms
(a 120 Hz target), so they keep the same duration regardless of how fast the
machine can redraw Tk. Includes easing curves, screen slide-in, toast
slide/fade, button "pop" pulses, modal fade-in, and smooth hover colour
tweens for every CTkButton (installed once via `install_smooth_hover`).
"""

import logging
import time
from typing import Any, Callable, Optional

logger = logging.getLogger("SocialApp.anim")

TICK_MS = 8  # ~120 Hz scheduling target


# ---------------------------------------------------------------- easing
def ease_out_cubic(t: float) -> float:
    return 1.0 - (1.0 - t) ** 3


def ease_in_out_cubic(t: float) -> float:
    return 4 * t * t * t if t < 0.5 else 1 - ((-2 * t + 2) ** 3) / 2


def ease_out_back(t: float) -> float:
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


# ------------------------------------------------------------ core loop
class AnimHandle:
    def __init__(self) -> None:
        self.after_id: Any = None
        self.cancelled = False

    def cancel(self, widget: Any = None) -> None:
        self.cancelled = True
        if widget is not None and self.after_id is not None:
            try:
                widget.after_cancel(self.after_id)
            except Exception:
                pass


def animate(
    widget: Any,
    duration_ms: int,
    step: Callable[[float], None],
    ease: Callable[[float], float] = ease_out_cubic,
    on_done: Optional[Callable[[], None]] = None,
) -> AnimHandle:
    """Run `step(eased_progress)` from 0 → 1 over `duration_ms` on widget's Tk loop."""
    handle = AnimHandle()
    start = time.perf_counter()

    def tick() -> None:
        if handle.cancelled:
            return
        try:
            if not widget.winfo_exists():
                return
            t = min(1.0, (time.perf_counter() - start) * 1000.0 / max(1, duration_ms))
            step(ease(t))
            if t < 1.0:
                handle.after_id = widget.after(TICK_MS, tick)
            elif on_done:
                on_done()
        except Exception as exc:  # never let an animation crash the UI
            logger.debug("animation aborted: %s", exc)
            if on_done:
                try:
                    on_done()
                except Exception:
                    pass

    tick()
    return handle


# --------------------------------------------------------------- colours
def _hex_to_rgb(color: str):
    color = color.strip()
    if color.startswith("#") and len(color) == 7:
        return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
    if color.startswith("#") and len(color) == 4:
        return tuple(int(c * 2, 16) for c in color[1:4])
    raise ValueError(color)


def lerp_color(c1: str, c2: str, t: float) -> str:
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    return "#%02x%02x%02x" % (
        int(r1 + (r2 - r1) * t),
        int(g1 + (g2 - g1) * t),
        int(b1 + (b2 - b1) * t),
    )


# ------------------------------------------------------- screen / widget
def slide_in(view: Any, dx: int = 28, duration_ms: int = 240) -> None:
    """Slide a placed view in from the right with an ease-out curve."""
    try:
        view.place(x=dx, y=0, relwidth=1.0, relheight=1.0)
    except Exception:
        return

    def step(p: float) -> None:
        view.place_configure(x=int(dx * (1.0 - p)))

    def done() -> None:
        try:
            view.place_configure(x=0)
        except Exception:
            pass

    animate(view, duration_ms, step, ease_out_cubic, done)


def fade_in_window(win: Any, duration_ms: int = 180) -> None:
    """Fade a toplevel in via -alpha. Always ends fully opaque, even on failure."""
    def force_opaque() -> None:
        try:
            win.attributes("-alpha", 1.0)
        except Exception:
            pass

    try:
        win.attributes("-alpha", 0.0)
    except Exception:
        return
    animate(win, duration_ms, lambda p: win.attributes("-alpha", max(0.0, min(1.0, p))), ease_out_cubic, force_opaque)
    try:
        win.after(duration_ms + 250, force_opaque)  # safety net
    except Exception:
        pass


def slide_down_toast(toast: Any, target_y: int = 50, from_y: int = -30, duration_ms: int = 260) -> None:
    def step(p: float) -> None:
        toast.place_configure(y=int(from_y + (target_y - from_y) * p))

    animate(toast, duration_ms, step, ease_out_back)


def slide_up_dismiss(toast: Any, target_y: int = -40, duration_ms: int = 200, on_done: Optional[Callable[[], None]] = None) -> None:
    try:
        start_y = int(toast.place_info().get("y", 50))
    except Exception:
        start_y = 50

    def step(p: float) -> None:
        toast.place_configure(y=int(start_y + (target_y - start_y) * p))

    animate(toast, duration_ms, step, ease_in_out_cubic, on_done)


def pop_button(btn: Any, base_size: int, family: str, weight: str = "bold", peak: float = 1.45, duration_ms: int = 320) -> None:
    """Heart-style bounce: scale the glyph up and settle back."""
    def step(p: float) -> None:
        # 0 → peak → 1.0 using a sine hump
        import math
        scale = 1.0 + (peak - 1.0) * math.sin(p * math.pi)
        btn.configure(font=(family, max(8, int(base_size * scale)), weight))

    def done() -> None:
        try:
            btn.configure(font=(family, base_size, weight))
        except Exception:
            pass

    animate(btn, duration_ms, step, ease_in_out_cubic, done)


# ------------------------------------------------------- smooth hover
_HOVER_INSTALLED = False


def install_smooth_hover(duration_ms: int = 140) -> None:
    """Patch CTkButton so hover colour changes tween instead of snapping."""
    global _HOVER_INSTALLED
    if _HOVER_INSTALLED:
        return
    try:
        import customtkinter as ctk
        Btn = ctk.CTkButton
        orig_enter, orig_leave = Btn._on_enter, Btn._on_leave
    except Exception:
        return

    def current_fill(btn: Any) -> Optional[str]:
        items = btn._canvas.find_withtag("inner_parts")
        if not items:
            return None
        return btn._canvas.itemcget(items[0], "fill")

    def tween(btn: Any, target: str) -> None:
        start = current_fill(btn)
        if not start or start == target:
            return
        _hex_to_rgb(start)
        _hex_to_rgb(target)  # raises -> caller falls back to instant

        prev = getattr(btn, "_hover_anim", None)
        if prev:
            prev.cancel(btn)

        def step(p: float) -> None:
            col = lerp_color(start, target, p)
            btn._canvas.itemconfig("inner_parts", outline=col, fill=col)
            if btn._text_label is not None:
                btn._text_label.configure(bg=col)
            if btn._image_label is not None:
                btn._image_label.configure(bg=col)

        btn._hover_anim = animate(btn, duration_ms, step, ease_out_cubic)

    def smooth_enter(self: Any, event: Any = None) -> None:
        try:
            if self._hover is True and self._state == "normal" and self._hover_color is not None:
                self._mouse_inside = True
                tween(self, self._apply_appearance_mode(self._hover_color))
                return
        except Exception:
            pass
        orig_enter(self, event)

    def smooth_leave(self: Any, event: Any = None) -> None:
        try:
            self._mouse_inside = False
            self._click_animation_running = False
            base = self._bg_color if self._fg_color == "transparent" else self._fg_color
            tween(self, self._apply_appearance_mode(base))
            return
        except Exception:
            pass
        orig_leave(self, event)

    Btn._on_enter = smooth_enter
    Btn._on_leave = smooth_leave
    _HOVER_INSTALLED = True

