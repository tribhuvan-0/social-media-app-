"""
Dual-tier LRU Image Cache for the SocialApp desktop client.
- Tier 1: In-memory LRU cache (OrderedDict, max 300 entries)
- Tier 2: On-disk cache directory (~/.cache/socialapp/images/) keyed by SHA-256
- High-quality Pillow anti-aliased circular masking and rounded thumbnail generation
- Non-blocking asynchronous loading with grey placeholder dispatch
"""

from collections import OrderedDict
import hashlib
import io
import logging
import os
from pathlib import Path
import threading
from typing import Any, Callable, Optional, Tuple, Union
import urllib.parse

from PIL import Image, ImageDraw, ImageFont, ImageOps

from .config import IMAGE_CACHE_DIR
from .async_utils import run_async

logger = logging.getLogger("SocialApp.cache")

# CustomTkinter CTkImage support detection
_HAS_CTK = False
CTkImage = None
try:
    import customtkinter as ctk
    if hasattr(ctk, "CTkImage"):
        CTkImage = ctk.CTkImage
        _HAS_CTK = True
except Exception:
    _HAS_CTK = False

# Cache Configuration
MAX_MEMORY_ENTRIES = 300

# Thread-safe in-memory LRU cache
_memory_cache: "OrderedDict[Tuple[str, int, int, bool, int], Any]" = OrderedDict()
_cache_lock = threading.Lock()


def _get_disk_cache_path(url_or_path: str) -> Path:
    """Derive deterministic on-disk path using SHA-256 hash of URL or path."""
    hasher = hashlib.sha256(url_or_path.encode("utf-8"))
    hex_digest = hasher.hexdigest()
    return IMAGE_CACHE_DIR / f"{hex_digest}.bin"


def create_circular_mask(width: int, height: int, super_sample: int = 4) -> Image.Image:
    """Generate high-quality anti-aliased alpha mask for circular avatars."""
    ss_w = max(1, width * super_sample)
    ss_h = max(1, height * super_sample)
    mask = Image.new("L", (ss_w, ss_h), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, ss_w, ss_h), fill=255)
    return mask.resize((width, height), Image.Resampling.LANCZOS)


def create_rounded_mask(width: int, height: int, radius: int, super_sample: int = 4) -> Image.Image:
    """Generate high-quality anti-aliased alpha mask with rounded corners."""
    ss_w = max(1, width * super_sample)
    ss_h = max(1, height * super_sample)
    ss_r = radius * super_sample
    mask = Image.new("L", (ss_w, ss_h), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, ss_w, ss_h), radius=ss_r, fill=255)
    return mask.resize((width, height), Image.Resampling.LANCZOS)


def apply_masks_and_scale(
    pil_img: Image.Image,
    target_size: Tuple[int, int],
    is_circular: bool = False,
    corner_radius: int = 0
) -> Image.Image:
    """
    Scale image maintaining or fitting aspect ratio, and apply circular or rounded corner alpha mask.
    """
    w, h = target_size
    # Fit into target size with high-quality downsampling
    img = ImageOps.fit(pil_img.convert("RGBA"), (w, h), Image.Resampling.LANCZOS)

    if is_circular:
        mask = create_circular_mask(w, h)
        img.putalpha(mask)
    elif corner_radius > 0:
        mask = create_rounded_mask(w, h, corner_radius)
        img.putalpha(mask)

    return img


def wrap_image(pil_img: Image.Image, size: Tuple[int, int]) -> Any:
    """Wrap PIL Image in CTkImage if CustomTkinter is available, else return PIL Image."""
    if _HAS_CTK and CTkImage is not None:
        return CTkImage(light_image=pil_img, dark_image=pil_img, size=size)
    return pil_img


def get_placeholder_image(
    size: Tuple[int, int],
    is_circular: bool = False,
    corner_radius: int = 0,
    color: str = "#262626",
    label: Optional[str] = None
) -> Any:
    """
    Generate an instant solid-color placeholder image.
    """
    w, h = size
    img = Image.new("RGBA", (w, h), color)
    if is_circular:
        img.putalpha(create_circular_mask(w, h))
    elif corner_radius > 0:
        img.putalpha(create_rounded_mask(w, h, corner_radius))

    if label:
        try:
            draw = ImageDraw.Draw(img)
            draw.text((w // 2, h // 2), label, fill="#888888", anchor="mm")
        except Exception:
            pass

    return wrap_image(img, size)


def load_raw_image_bytes(url_or_path: str) -> Optional[bytes]:
    """
    Load raw byte payload from disk cache, local file path, or remote URL.
    Saves remote downloads into disk cache.
    """
    if not url_or_path:
        return None

    # Check local filesystem first
    p = Path(url_or_path)
    if p.exists() and p.is_file():
        try:
            return p.read_bytes()
        except Exception as e:
            logger.warning("Failed to read local file %s: %s", url_or_path, e)

    # Check Tier-2 disk cache
    disk_path = _get_disk_cache_path(url_or_path)
    if disk_path.exists():
        try:
            return disk_path.read_bytes()
        except Exception:
            pass

    # Remote URL download
    if url_or_path.startswith("http://") or url_or_path.startswith("https://"):
        try:
            import requests
            resp = requests.get(url_or_path, timeout=10.0)
            if resp.status_code == 200:
                raw_bytes = resp.content
                # Write to disk cache
                try:
                    disk_path.parent.mkdir(parents=True, exist_ok=True)
                    disk_path.write_bytes(raw_bytes)
                except Exception as e:
                    logger.warning("Failed to write disk cache for %s: %s", url_or_path, e)
                return raw_bytes
        except Exception as e:
            logger.warning("Failed to download image from %s: %s", url_or_path, e)

    return None


def get_image_sync(
    url_or_path: str,
    size: Tuple[int, int],
    is_circular: bool = False,
    corner_radius: int = 0
) -> Optional[Any]:
    """
    Synchronously retrieve processed image from memory LRU cache, disk cache, or remote URL.
    Returns wrapped CTkImage or PIL Image, or None on failure.
    """
    w, h = size
    cache_key = (url_or_path, w, h, is_circular, corner_radius)

    # Check Tier-1 memory cache
    with _cache_lock:
        if cache_key in _memory_cache:
            _memory_cache.move_to_end(cache_key)
            return _memory_cache[cache_key]

    # Load bytes and process
    raw_bytes = load_raw_image_bytes(url_or_path)
    if not raw_bytes:
        return None

    try:
        pil_src = Image.open(io.BytesIO(raw_bytes))
        processed_pil = apply_masks_and_scale(pil_src, size, is_circular, corner_radius)
        wrapped = wrap_image(processed_pil, size)

        # Store in Tier-1 memory cache
        with _cache_lock:
            _memory_cache[cache_key] = wrapped
            if len(_memory_cache) > MAX_MEMORY_ENTRIES:
                _memory_cache.popitem(last=False)

        return wrapped
    except Exception as e:
        logger.warning("Failed to decode image from %s: %s", url_or_path, e)
        return None


def load_image_async(
    url_or_path: str,
    size: Tuple[int, int],
    is_circular: bool = False,
    corner_radius: int = 0,
    on_ready: Optional[Callable[[Any], None]] = None,
    placeholder_color: str = "#262626"
) -> Any:
    """
    Non-blocking image loader. Immediately returns an instant placeholder image,
    and submits a worker job to fetch/decode the full image. When ready,
    invokes on_ready(wrapped_image) on the main thread via async_utils.run_async.
    """
    w, h = size
    cache_key = (url_or_path, w, h, is_circular, corner_radius)

    # Fast memory cache hit
    with _cache_lock:
        if cache_key in _memory_cache:
            _memory_cache.move_to_end(cache_key)
            cached_item = _memory_cache[cache_key]
            if on_ready:
                # Dispatch immediately or call
                on_ready(cached_item)
            return cached_item

    placeholder = get_placeholder_image(size, is_circular, corner_radius, color=placeholder_color)

    if not url_or_path:
        return placeholder

    def worker_fetch() -> Optional[Any]:
        # Off-thread fetch and PIL transform
        raw = load_raw_image_bytes(url_or_path)
        if not raw:
            return None
        pil_src = Image.open(io.BytesIO(raw))
        return apply_masks_and_scale(pil_src, size, is_circular, corner_radius)

    def on_worker_success(pil_result: Optional[Image.Image]) -> None:
        if pil_result is None:
            return
        wrapped = wrap_image(pil_result, size)
        with _cache_lock:
            _memory_cache[cache_key] = wrapped
            if len(_memory_cache) > MAX_MEMORY_ENTRIES:
                _memory_cache.popitem(last=False)
        if on_ready:
            on_ready(wrapped)

    run_async(worker_fetch, on_success=on_worker_success)
    return placeholder


def clear_memory_cache() -> None:
    """Empty the in-memory LRU cache."""
    with _cache_lock:
        _memory_cache.clear()


def clear_disk_cache() -> None:
    """Purge all cached image files from disk."""
    try:
        for item in IMAGE_CACHE_DIR.glob("*.bin"):
            try:
                item.unlink(missing_ok=True)
            except Exception:
                pass
    except Exception:
        pass


def get_disk_cache_size() -> int:
    """Return total bytes occupied by on-disk cached images."""
    total = 0
    try:
        for item in IMAGE_CACHE_DIR.glob("*.bin"):
            try:
                total += item.stat().st_size
            except Exception:
                pass
    except Exception:
        pass
    return total
