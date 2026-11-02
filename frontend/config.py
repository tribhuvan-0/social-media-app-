"""
Configuration management for the SocialApp desktop client.
Handles environment variables, endpoints, timeouts, cache paths, and persistent settings.
"""

import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, Optional
import urllib.request
import urllib.error

# Network & API Defaults
DEFAULT_API_BASE_URL = "http://localhost:8080/api"
API_BASE_URL = os.getenv("API_BASE_URL", os.getenv("BASE_URL", DEFAULT_API_BASE_URL)).rstrip("/")

# Flag indicating whether mock mode is forced via environment or CLI argument
USE_MOCK = os.getenv("USE_MOCK", "0").lower() in ("1", "true", "yes") or ("--mock" in sys.argv)

# Request Timeouts in seconds
TIMEOUT_NORMAL = 10.0
TIMEOUT_UPLOAD = 120.0

# Window Dimensions & Metadata
WINDOW_WIDTH = 480
WINDOW_HEIGHT = 860
WINDOW_TITLE = "SocialApp"

# Storage & Cache Directories
CACHE_DIR = Path.home() / ".cache" / "socialapp"
IMAGE_CACHE_DIR = CACHE_DIR / "images"
CONFIG_DIR = Path.home() / ".socialapp"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Appearance & Theme Settings
DEFAULT_APPEARANCE_MODE = "dark"
VALID_APPEARANCE_MODES = ("dark", "light", "system")

# Ensure required directories exist
try:
    IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass


def load_config() -> Dict[str, Any]:
    """
    Load saved persistent settings from CONFIG_FILE (~/.socialapp/config.json).
    Returns default dictionary if file is missing or corrupted.
    """
    defaults: Dict[str, Any] = {
        "appearance_mode": DEFAULT_APPEARANCE_MODE,
        "api_base_url": API_BASE_URL,
        "use_mock": USE_MOCK,
        "volume": 80,
        "is_muted": False,
    }
    if not CONFIG_FILE.exists():
        return defaults

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                defaults.update(data)
    except Exception:
        pass
    return defaults


def save_config(config_dict: Dict[str, Any]) -> bool:
    """
    Persist configuration dictionary to CONFIG_FILE.
    """
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_dict, f, indent=2)
        return True
    except Exception:
        return False


def get_setting(key: str, default: Any = None) -> Any:
    """
    Retrieve a single persistent setting value.
    """
    cfg = load_config()
    return cfg.get(key, default)


def set_setting(key: str, value: Any) -> bool:
    """
    Update and persist a single configuration value.
    """
    cfg = load_config()
    cfg[key] = value
    return save_config(cfg)


def is_backend_reachable(base_url: Optional[str] = None, timeout: float = 1.5) -> bool:
    """
    Perform a quick lightweight probe to determine if the backend REST server is reachable.
    """
    target_url = base_url or API_BASE_URL
    # Probe root or auth endpoint
    probe_url = target_url.rstrip("/") + "/auth/me"
    try:
        req = urllib.request.Request(
            probe_url,
            headers={"User-Agent": "SocialApp-Client-Probe"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status < 500
    except urllib.error.HTTPError as e:
        # HTTP 401 or 403 means the server is up and responsive!
        return e.code in (401, 403, 200, 404)
    except Exception:
        return False
