"""
Instagram Dark & Light theme definitions, colors, typography, and CustomTkinter widget styling helpers.
"""

from typing import Any, Dict, Optional, Tuple

# Color Palettes
THEMES: Dict[str, Dict[str, Any]] = {
    "dark": {
        "bg": "#000000",
        "surface": "#121212",
        "surface_elevated": "#1E1E1E",
        "card": "#181818",
        "card_hover": "#222222",
        "border": "#262626",
        "divider": "#2F2F2F",
        "primary": "#0095F6",
        "primary_hover": "#1877F2",
        "text_primary": "#FFFFFF",
        "text_secondary": "#A8A8A8",
        "text_muted": "#737373",
        "text_placeholder": "#555555",
        "accent": "#0095F6",
        "danger": "#FF3040",
        "danger_hover": "#D92737",
        "like_red": "#FF3040",
        "story_ring_seen": "#3A3A3A",
        "story_gradient": ["#F9CE34", "#EE2A7B", "#6228D7"],
        "overlay": "#1A1A1A",
    },
    "light": {
        "bg": "#FFFFFF",
        "surface": "#FAFAFA",
        "surface_elevated": "#F0F0F0",
        "card": "#FFFFFF",
        "card_hover": "#F5F5F5",
        "border": "#DBDBDB",
        "divider": "#E8E8E8",
        "primary": "#0095F6",
        "primary_hover": "#1877F2",
        "text_primary": "#000000",
        "text_secondary": "#737373",
        "text_muted": "#8E8E8E",
        "text_placeholder": "#A8A8A8",
        "accent": "#0095F6",
        "danger": "#ED4956",
        "danger_hover": "#C63C47",
        "like_red": "#ED4956",
        "story_ring_seen": "#DBDBDB",
        "story_gradient": ["#F9CE34", "#EE2A7B", "#6228D7"],
        "overlay": "#E0E0E0",
    },
}

# Geometric Radii
RADIUS_CARD = 20
RADIUS_BUTTON = 18
RADIUS_ENTRY = 16
RADIUS_CHIP = 18
RADIUS_AVATAR = 999  # Circular

# Typography Definitions
FALLBACK_FONT_FAMILIES = ("Inter", "SF Pro Text", "Segoe UI", "Noto Sans", "Cantarell", "Helvetica", "DejaVu Sans", "Arial")


def _detect_font_family() -> str:
    """Pick the best installed UI font (Inter > Segoe UI > Noto Sans > ...)."""
    import platform
    import subprocess
    if platform.system() != "Linux":
        return "Segoe UI" if platform.system() == "Windows" else "Helvetica Neue"
    try:
        out = subprocess.run(["fc-list", ":", "family"], capture_output=True, text=True, timeout=3).stdout
        installed = {f.strip().lower() for line in out.splitlines() for f in line.split(",")}
        for fam in FALLBACK_FONT_FAMILIES:
            if fam.lower() in installed:
                return fam
    except Exception:
        pass
    return "DejaVu Sans"


UI_FONT = _detect_font_family()
FONT_FAMILY = UI_FONT


def get_theme_colors(mode: str = "dark") -> Dict[str, Any]:
    """Get color mapping dictionary for specified appearance mode."""
    normalized = mode.lower() if mode else "dark"
    if normalized not in THEMES:
        normalized = "dark"
    return THEMES[normalized]


def get_color(name: str, mode: str = "dark") -> str:
    """Retrieve a single color code by name and mode."""
    palette = get_theme_colors(mode)
    return str(palette.get(name, "#000000"))


def font_spec(size: int, weight: str = "normal", family: Optional[str] = None) -> Tuple[str, int, str]:
    """Generate Tk/CTk compatible font specification tuple."""
    return (family or FONT_FAMILY, size, weight)


def font_logo() -> Tuple[str, int, str]:
    return font_spec(24, "bold")


def font_h1() -> Tuple[str, int, str]:
    return font_spec(20, "bold")


def font_h2() -> Tuple[str, int, str]:
    return font_spec(16, "bold")


def font_body(bold: bool = False) -> Tuple[str, int, str]:
    return font_spec(14, "bold" if bold else "normal")


def font_caption(bold: bool = False) -> Tuple[str, int, str]:
    return font_spec(12, "bold" if bold else "normal")


def font_small() -> Tuple[str, int, str]:
    return font_spec(11, "normal")


# CTk Widget Styling Helpers
def style_primary_button(btn: Any, mode: str = "dark") -> None:
    """Apply Instagram blue primary button styles to a CTkButton."""
    colors = get_theme_colors(mode)
    try:
        btn.configure(
            fg_color=colors["primary"],
            hover_color=colors["primary_hover"],
            text_color="#FFFFFF",
            corner_radius=RADIUS_BUTTON,
            font=font_body(bold=True),
        )
    except Exception:
        pass


def style_secondary_button(btn: Any, mode: str = "dark") -> None:
    """Apply muted/secondary button styles to a CTkButton."""
    colors = get_theme_colors(mode)
    try:
        btn.configure(
            fg_color=colors["surface_elevated"],
            hover_color=colors["card_hover"],
            text_color=colors["text_primary"],
            border_color=colors["border"],
            border_width=1,
            corner_radius=RADIUS_BUTTON,
            font=font_body(bold=True),
        )
    except Exception:
        pass


def style_danger_button(btn: Any, mode: str = "dark") -> None:
    """Apply red danger button styles to a CTkButton."""
    colors = get_theme_colors(mode)
    try:
        btn.configure(
            fg_color=colors["danger"],
            hover_color=colors["danger_hover"],
            text_color="#FFFFFF",
            corner_radius=RADIUS_BUTTON,
            font=font_body(bold=True),
        )
    except Exception:
        pass


def style_entry(entry: Any, mode: str = "dark") -> None:
    """Apply Instagram border & surface entry styles to a CTkEntry."""
    colors = get_theme_colors(mode)
    try:
        entry.configure(
            fg_color=colors["surface"],
            border_color=colors["border"],
            text_color=colors["text_primary"],
            placeholder_text_color=colors["text_placeholder"],
            corner_radius=RADIUS_ENTRY,
            border_width=1,
            font=font_body(bold=False),
        )
    except Exception:
        pass


def style_card(frame: Any, mode: str = "dark") -> None:
    """Apply rounded card background and border to a CTkFrame."""
    colors = get_theme_colors(mode)
    try:
        frame.configure(
            fg_color=colors["card"],
            border_color=colors["border"],
            border_width=1,
            corner_radius=RADIUS_CARD,
        )
    except Exception:
        pass
