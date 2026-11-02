"""
Single shared video player for the SocialApp desktop client.
Embeds VLC into Tkinter/CustomTkinter frames across Linux (X11), Windows (HWND), and macOS (NSObject).
Includes deadlock-prevention event dispatching and a comprehensive MockVlcPlayer fallback
for environments lacking VLC or native display libraries.
"""

import logging
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
from typing import Any, Callable, Optional

try:
    import tkinter as tk
    from PIL import Image, ImageTk
    _HAS_TK_PIL = True
except Exception:
    tk = None
    Image = None
    ImageTk = None
    _HAS_TK_PIL = False

from .theme import UI_FONT

logger = logging.getLogger("SocialApp.player")
_HAS_FFMPEG = shutil.which("ffmpeg") is not None

# Attempt VLC native binding import
_HAS_VLC = False
vlc = None
try:
    import vlc as _vlc
    # Test instantiation to catch missing libvlc.so
    _test_inst = _vlc.Instance("--no-xlib", "--quiet")
    if _test_inst is not None:
        vlc = _vlc
        _HAS_VLC = True
except Exception as e:
    logger.info("VLC native library unavailable (%s). MockVlcPlayer fallback will be used.", e)
    _HAS_VLC = False


def _resolve_local_media(url: str, stop_ev: Any) -> Optional[str]:
    """
    Return a local file path for `url`. HTTP(S) sources are downloaded once into
    ~/.cache/socialapp/video (the backend's range handling breaks FFmpeg seeking
    for MP4s whose moov atom sits at the end of the file).
    """
    if not url.startswith(("http://", "https://")):
        return url[7:] if url.startswith("file://") else url
    import hashlib
    import tempfile
    cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "socialapp", "video")
    os.makedirs(cache_dir, exist_ok=True)
    ext = os.path.splitext(url.split("?")[0])[1] or ".mp4"
    dest = os.path.join(cache_dir, hashlib.sha1(url.encode()).hexdigest() + ext)
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return dest
    try:
        import requests
        with requests.get(url, stream=True, timeout=15) as r:
            r.raise_for_status()
            fd, tmp = tempfile.mkstemp(dir=cache_dir)
            with os.fdopen(fd, "wb") as f:
                for chunk in r.iter_content(65536):
                    if stop_ev.is_set():
                        os.unlink(tmp)
                        return None
                    f.write(chunk)
        os.replace(tmp, dest)
        return dest
    except Exception as e:
        logger.warning("Video download failed for %s: %s", url, e)
        return None


class BasePlayer:
    """Abstract interface for SocialApp video players."""

    def attach_to_widget(self, widget: Any) -> None:
        raise NotImplementedError

    def play_url(
        self,
        url: str,
        widget: Any = None,
        loop: bool = False,
        on_end: Optional[Callable[[], None]] = None,
        on_playing: Optional[Callable[[], None]] = None
    ) -> bool:
        raise NotImplementedError

    def play(self) -> None:
        raise NotImplementedError

    def pause(self) -> None:
        raise NotImplementedError

    def resume(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def toggle_pause(self) -> None:
        raise NotImplementedError

    def seek(self, position_pct: float) -> None:
        raise NotImplementedError

    def seek_time_ms(self, time_ms: int) -> None:
        raise NotImplementedError

    def get_time(self) -> int:
        raise NotImplementedError

    def get_length(self) -> int:
        raise NotImplementedError

    def is_playing(self) -> bool:
        raise NotImplementedError

    def set_volume(self, volume: int) -> None:
        raise NotImplementedError

    def get_volume(self) -> int:
        raise NotImplementedError

    def mute(self) -> None:
        raise NotImplementedError

    def unmute(self) -> None:
        raise NotImplementedError

    def toggle_mute(self) -> bool:
        raise NotImplementedError

    def release(self) -> None:
        raise NotImplementedError


class SharedVlcPlayer(BasePlayer):
    """
    Production VLC player wrapper managing a single shared native MediaPlayer.
    Embeds directly into Tkinter frame windows and prevents deadlocks by routing
    all VLC event callbacks onto Tkinter's main thread via root.after(0, ...).
    """

    def __init__(self, root: Any = None) -> None:
        if not _HAS_VLC or vlc is None:
            raise RuntimeError("Cannot initialize SharedVlcPlayer without native VLC.")

        self._root = root
        self._current_widget: Any = None
        self._current_url: Optional[str] = None
        self._loop: bool = False
        self._on_end: Optional[Callable[[], None]] = None
        self._on_playing: Optional[Callable[[], None]] = None
        self._volume: int = 80
        self._is_muted: bool = False

        # Frame-renderer state for Linux / Wayland / CustomTkinter canvas compatibility
        self._use_frame_renderer: bool = (
            platform.system() == "Linux" and _HAS_FFMPEG and _HAS_TK_PIL
        )
        self._video_surface: Any = None
        self._surface_parent: Any = None
        self._frame_proc: Optional[subprocess.Popen] = None
        self._frame_thread: Optional[threading.Thread] = None
        self._frame_stop_event = threading.Event()
        self._frame_paused: bool = False
        self._playback_gen: int = 0
        self._photo_ref: Any = None
        self._latest_pil_frame: Any = None
        self._pump_timer_id: Any = None
        self._sw_start_time: float = 0.0
        self._sw_elapsed_ms: int = 0
        self._sw_duration_ms: int = 5000

        # Initialize VLC instance & player
        args = ["--quiet", "--no-video-title-show"]
        if platform.system() == "Linux":
            if self._use_frame_renderer:
                # Let FFmpeg render frames directly onto Tk Label so CustomTkinter
                # overlay buttons stay visible on top and XWayland/VDPAU never black-screens
                args.append("--no-video")
            else:
                args.extend(["--avcodec-hw=none", "--vout=xcb_x11,x11,glx,any"])
        self._instance = vlc.Instance(*args)
        self._media_player = self._instance.media_player_new()

        # Wire VLC event callbacks
        self._event_manager = self._media_player.event_manager()
        self._event_manager.event_attach(
            vlc.EventType.MediaPlayerEndReached,
            self._vlc_callback_end_reached
        )
        self._event_manager.event_attach(
            vlc.EventType.MediaPlayerPlaying,
            self._vlc_callback_playing
        )
        self.set_volume(self._volume)

    def set_root(self, root: Any) -> None:
        self._root = root

    def _ensure_video_surface(self, widget: Any) -> Any:
        """
        Create or attach a native tk.Label inside `widget` positioned immediately
        above `widget._canvas` (so CTkFrame's canvas does not occlude it) and
        beneath all overlay buttons/labels (like Reels sidebar and Stories top bar).
        """
        if not _HAS_TK_PIL or widget is None or not hasattr(widget, "tk"):
            return None

        try:
            if self._video_surface is not None and self._surface_parent == widget:
                if self._video_surface.winfo_exists():
                    self._video_surface.place(relx=0, rely=0, relwidth=1.0, relheight=1.0)
                    if hasattr(widget, "_canvas"):
                        self._video_surface.lift(widget._canvas)
                    return self._video_surface
        except Exception:
            pass

        # Clean up previous surface if attached to a different widget
        if self._video_surface is not None:
            try:
                if self._video_surface.winfo_exists():
                    self._video_surface.destroy()
            except Exception:
                pass
            self._video_surface = None

        try:
            surface = tk.Label(widget, bg="#000000", bd=0, highlightthickness=0)
            surface.place(relx=0, rely=0, relwidth=1.0, relheight=1.0)
            if hasattr(widget, "_canvas"):
                surface.lift(widget._canvas)
            else:
                surface.lower()

            # Forward mouse/scroll events to the widget that owns the bindings.
            # CTk widgets register their bindings on the internal canvas, so events
            # must be generated there (not on the frame itself).
            target = getattr(widget, "_canvas", widget)

            def _forward(name: str):
                def handler(e: Any) -> str:
                    try:
                        if name == "<MouseWheel>":
                            target.event_generate(name, x=e.x, y=e.y, delta=getattr(e, "delta", 0))
                        else:
                            target.event_generate(name, x=e.x, y=e.y)
                    except Exception:
                        pass
                    return "break"
                return handler

            for ev in ("<Button-1>", "<ButtonPress-1>", "<ButtonRelease-1>", "<Double-Button-1>", "<MouseWheel>", "<Button-4>", "<Button-5>"):
                surface.bind(ev, _forward(ev))

            self._video_surface = surface
            self._surface_parent = widget
            return surface
        except Exception as e:
            logger.debug("Could not create video surface label: %s", e)
            return None

    def detach_surface(self, widget: Any = None) -> None:
        """Remove the video surface (optionally only if it belongs to `widget`)."""
        if widget is not None and self._surface_parent is not widget:
            return
        self._stop_frame_renderer()
        if self._video_surface is not None:
            try:
                self._video_surface.destroy()
            except Exception:
                pass
        self._video_surface = None
        self._surface_parent = None

    def is_active_on(self, widget: Any) -> bool:
        """True while the frame renderer is live (playing or paused) inside `widget`."""
        return (
            self._surface_parent is widget
            and self._frame_proc is not None
            and not self._frame_stop_event.is_set()
        )

    def _stop_frame_renderer(self) -> None:
        self._playback_gen = getattr(self, "_playback_gen", 0) + 1
        self._frame_stop_event.set()
        self._latest_pil_frame = None
        if self._pump_timer_id is not None and self._root is not None:
            try:
                self._root.after_cancel(self._pump_timer_id)
            except Exception:
                pass
            self._pump_timer_id = None
        proc = self._frame_proc
        self._frame_proc = None
        if proc is not None:
            try:
                proc.terminate()
            except Exception:
                pass

    def _start_frame_renderer(self, url: str, widget: Any, loop: bool) -> None:
        self._stop_frame_renderer()
        if not self._use_frame_renderer or widget is None or not hasattr(widget, "tk"):
            return

        surface = self._ensure_video_surface(widget)
        if surface is None:
            return

        self._frame_stop_event = threading.Event()
        self._frame_paused = False
        self._latest_pil_frame = None
        self._playback_gen += 1
        gen = self._playback_gen
        stop_ev = self._frame_stop_event
        self._sw_start_time = time.time()
        self._sw_elapsed_ms = 0

        try:
            widget.update_idletasks()
            w = max(240, int(widget.winfo_width() or 440))
            h = max(240, int(widget.winfo_height() or 640))
        except Exception:
            w, h = 440, 640

        # Ensure even dimensions for video scaling
        w = (w // 2) * 2
        h = (h // 2) * 2

        def _reader_loop() -> None:
            fps = 24
            frame_interval = 1.0 / fps
            frame_bytes = w * h * 3

            src = _resolve_local_media(url, stop_ev)
            if src is None or stop_ev.is_set() or self._playback_gen != gen:
                return

            # Start VLC audio on the resolved local file so HTTP range bugs never break audio
            try:
                if self._media_player is not None:
                    media = self._instance.media_new(src)
                    if loop:
                        media.add_option("input-repeat=65535")
                    self._media_player.set_media(media)
                    self._media_player.play()
                    self._apply_audio_state()
            except Exception as e:
                logger.debug("VLC local audio start warning: %s", e)

            while not stop_ev.is_set() and self._playback_gen == gen:
                cmd = [
                    "ffmpeg",
                    "-nostdin",
                    "-loglevel", "error",
                ]
                if loop:
                    cmd.extend(["-stream_loop", "-1"])
                cmd.extend([
                    "-i", src,
                    "-vf", f"fps={fps},scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black",
                    "-f", "rawvideo",
                    "-pix_fmt", "rgb24",
                    "-"
                ])
                try:
                    proc = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        bufsize=frame_bytes * 2
                    )
                    self._frame_proc = proc
                except Exception as e:
                    logger.warning("FFmpeg frame renderer failed to start: %s", e)
                    return

                next_frame_t = time.time()
                try:
                    while not stop_ev.is_set() and self._playback_gen == gen:
                        if self._frame_paused:
                            time.sleep(0.04)
                            next_frame_t = time.time()
                            continue

                        raw = proc.stdout.read(frame_bytes) if proc.stdout else b""
                        if len(raw) < frame_bytes:
                            break

                        self._latest_pil_frame = Image.frombytes("RGB", (w, h), raw)
                        self._sw_elapsed_ms += int(1000 / fps)

                        next_frame_t += frame_interval
                        sleep_s = next_frame_t - time.time()
                        if sleep_s > 0:
                            time.sleep(sleep_s)
                        else:
                            next_frame_t = time.time()
                except Exception:
                    pass
                finally:
                    try:
                        proc.terminate()
                        proc.wait(timeout=0.5)
                    except Exception:
                        pass

                if not loop or stop_ev.is_set() or self._playback_gen != gen:
                    break

        t = threading.Thread(target=_reader_loop, daemon=True)
        self._frame_thread = t
        t.start()
        self._start_main_thread_pump(surface, gen)

    def _start_main_thread_pump(self, surface: Any, gen: int) -> None:
        target = self._root or surface
        if target is None or not hasattr(target, "after"):
            return

        def _pump() -> None:
            if self._playback_gen != gen or self._frame_stop_event.is_set():
                return
            try:
                if not surface.winfo_exists():
                    return
                pil_img = self._latest_pil_frame
                if pil_img is not None:
                    self._latest_pil_frame = None
                    photo = ImageTk.PhotoImage(pil_img)
                    surface.configure(image=photo)
                    surface.image = photo
                    self._photo_ref = photo
                self._apply_audio_state()
            except Exception:
                pass
            try:
                self._pump_timer_id = target.after(33, _pump)
            except Exception:
                pass

        try:
            self._pump_timer_id = target.after(16, _pump)
        except Exception:
            pass

    def attach_to_widget(self, widget: Any) -> None:
        """
        Embed the VLC player into a Tkinter / CustomTkinter frame widget.
        Flushes idle tasks to ensure a valid native window handle exists.
        """
        if widget is None:
            return

        self._current_widget = widget
        if self._use_frame_renderer and hasattr(widget, "tk"):
            self._ensure_video_surface(widget)
            return

        try:
            widget.update_idletasks()
            target_widget = getattr(widget, "_canvas", widget)
            win_id = target_widget.winfo_id()
            os_name = platform.system()

            if os_name == "Windows":
                self._media_player.set_hwnd(win_id)
            elif os_name == "Darwin":
                self._media_player.set_nsobject(win_id)
            else:
                # Linux / X11 / XWayland
                self._media_player.set_xwindow(win_id)
        except Exception as e:
            logger.warning("Failed to attach native window handle to widget: %s", e)

    def play_url(
        self,
        url: str,
        widget: Any = None,
        loop: bool = False,
        on_end: Optional[Callable[[], None]] = None,
        on_playing: Optional[Callable[[], None]] = None
    ) -> bool:
        """
        Load and start playing media from the given URL or file path.
        """
        self.stop()
        self._current_url = url
        self._loop = loop
        self._on_end = on_end
        self._on_playing = on_playing

        if widget is not None:
            self.attach_to_widget(widget)

        target_widget = widget or self._current_widget
        if self._use_frame_renderer and target_widget is not None and hasattr(target_widget, "tk"):
            self._start_frame_renderer(url, target_widget, loop)
            return True

        try:
            local_or_url = _resolve_local_media(url, self._frame_stop_event) or url
            media = self._instance.media_new(local_or_url)
            if loop:
                media.add_option("input-repeat=65535")
            self._media_player.set_media(media)
            self._media_player.play()
            self._apply_audio_state()
            return True
        except Exception as e:
            logger.error("Failed to play media URL %s: %s", url, e)
            return False

    def _apply_audio_state(self) -> None:
        if not self._media_player:
            return
        try:
            if self._is_muted:
                self._media_player.audio_set_mute(True)
                self._media_player.audio_set_volume(0)
            else:
                self._media_player.audio_set_mute(False)
                self._media_player.audio_set_volume(self._volume)
        except Exception:
            pass

    def play(self) -> None:
        self._frame_paused = False
        if self._media_player:
            try:
                self._media_player.set_pause(0)
                self._media_player.play()
                self._apply_audio_state()
            except Exception:
                pass

    def pause(self) -> None:
        self._frame_paused = True
        if self._media_player:
            try:
                self._media_player.set_pause(1)
            except Exception:
                pass

    def resume(self) -> None:
        self._frame_paused = False
        if self._media_player:
            try:
                self._media_player.set_pause(0)
                if not self._media_player.is_playing():
                    self._media_player.play()
                self._apply_audio_state()
            except Exception:
                pass

    def stop(self) -> None:
        self._stop_frame_renderer()
        if self._media_player:
            try:
                self._media_player.stop()
            except Exception:
                pass

    def toggle_pause(self) -> None:
        if self.is_playing():
            self.pause()
        else:
            self.resume()

    def seek(self, position_pct: float) -> None:
        """Seek to position percentage (0.0 to 1.0)."""
        if self._media_player:
            clamped = max(0.0, min(1.0, position_pct))
            self._media_player.set_position(clamped)

    def seek_time_ms(self, time_ms: int) -> None:
        """Seek to timestamp in milliseconds."""
        if self._media_player:
            self._media_player.set_time(max(0, time_ms))

    def get_time(self) -> int:
        """Return current playback position in milliseconds."""
        if self._media_player:
            t = self._media_player.get_time()
            if t > 0:
                return t
        return self._sw_elapsed_ms

    def get_length(self) -> int:
        """Return total duration in milliseconds."""
        if self._media_player:
            l = self._media_player.get_length()
            if l > 0:
                return l
        return self._sw_duration_ms

    def is_playing(self) -> bool:
        if self._frame_proc is not None and not self._frame_stop_event.is_set():
            return not self._frame_paused
        if self._media_player:
            return bool(self._media_player.is_playing())
        return False

    def set_volume(self, volume: int) -> None:
        self._volume = max(0, min(100, volume))
        if self._volume > 0:
            self._is_muted = False
        self._apply_audio_state()

    def get_volume(self) -> int:
        return self._volume

    def mute(self) -> None:
        self._is_muted = True
        self._apply_audio_state()

    def unmute(self) -> None:
        self._is_muted = False
        if self._volume == 0:
            self._volume = 80
        self._apply_audio_state()

    def toggle_mute(self) -> bool:
        if self._is_muted:
            self.unmute()
        else:
            self.mute()
        return self._is_muted

    def release(self) -> None:
        self.stop()
        if self._media_player:
            try:
                self._media_player.release()
            except Exception:
                pass
            self._media_player = None

    # VLC Event Listeners (C-thread callbacks -> Dispatch to main thread)
    def _vlc_callback_end_reached(self, event: Any) -> None:
        if self._root:
            try:
                self._root.after(0, self._handle_main_thread_end_reached)
            except Exception:
                pass
        else:
            self._handle_main_thread_end_reached()

    def _vlc_callback_playing(self, event: Any) -> None:
        if self._root:
            try:
                self._root.after(0, self._handle_main_thread_playing)
            except Exception:
                pass
        else:
            self._handle_main_thread_playing()

    def _handle_main_thread_end_reached(self) -> None:
        if self._loop:
            # Replay video in loop mode
            if self._media_player:
                self._media_player.set_position(0.0)
                self._media_player.play()
        if self._on_end:
            try:
                self._on_end()
            except Exception as e:
                logger.error("Error in on_end callback: %s", e)

    def _handle_main_thread_playing(self) -> None:
        if self._on_playing:
            try:
                self._on_playing()
            except Exception as e:
                logger.error("Error in on_playing callback: %s", e)


class MockVlcPlayer(BasePlayer):
    """
    Robust fallback player simulating playback state and time progression.
    Guarantees that video views, reels, and stories execute without crashes
    on headless servers, machines without VLC installed, or CI environments.
    """

    def __init__(self, root: Any = None) -> None:
        self._root = root
        self._widget: Any = None
        self._url: Optional[str] = None
        self._loop: bool = False
        self._on_end: Optional[Callable[[], None]] = None
        self._on_playing: Optional[Callable[[], None]] = None

        self._is_playing: bool = False
        self._is_muted: bool = False
        self._volume: int = 80
        self._duration_ms: int = 15000  # Default simulated length 15s
        self._current_time_ms: int = 0
        self._last_tick: float = 0.0
        self._timer_id: Optional[str] = None
        self._lock = threading.Lock()

    def set_root(self, root: Any) -> None:
        self._root = root

    def detach_surface(self, widget: Any = None) -> None:
        pass

    def is_active_on(self, widget: Any) -> bool:
        return self._is_playing and self._widget is widget

    def attach_to_widget(self, widget: Any) -> None:
        self._widget = widget
        self._render_placeholder()

    def play_url(
        self,
        url: str,
        widget: Any = None,
        loop: bool = False,
        on_end: Optional[Callable[[], None]] = None,
        on_playing: Optional[Callable[[], None]] = None
    ) -> bool:
        self.stop()
        self._url = url
        self._loop = loop
        self._on_end = on_end
        self._on_playing = on_playing
        self._current_time_ms = 0

        if widget is not None:
            self.attach_to_widget(widget)

        self._is_playing = True
        self._last_tick = time.time()
        self._schedule_tick()

        if self._on_playing:
            if self._root:
                self._root.after(50, self._on_playing)
            else:
                self._on_playing()
        return True

    def play(self) -> None:
        if not self._is_playing:
            self._is_playing = True
            self._last_tick = time.time()
            self._schedule_tick()

    def pause(self) -> None:
        self._is_playing = False
        self._cancel_tick()
        self._render_placeholder()

    def resume(self) -> None:
        self.play()

    def stop(self) -> None:
        self._is_playing = False
        self._cancel_tick()
        self._current_time_ms = 0
        self._render_placeholder()

    def toggle_pause(self) -> None:
        if self._is_playing:
            self.pause()
        else:
            self.resume()

    def seek(self, position_pct: float) -> None:
        clamped = max(0.0, min(1.0, position_pct))
        self._current_time_ms = int(clamped * self._duration_ms)
        self._render_placeholder()

    def seek_time_ms(self, time_ms: int) -> None:
        self._current_time_ms = max(0, min(self._duration_ms, time_ms))
        self._render_placeholder()

    def get_time(self) -> int:
        return self._current_time_ms

    def get_length(self) -> int:
        return self._duration_ms

    def is_playing(self) -> bool:
        return self._is_playing

    def set_volume(self, volume: int) -> None:
        self._volume = max(0, min(100, volume))

    def get_volume(self) -> int:
        return self._volume

    def mute(self) -> None:
        self._is_muted = True

    def unmute(self) -> None:
        self._is_muted = False

    def toggle_mute(self) -> bool:
        self._is_muted = not self._is_muted
        return self._is_muted

    def release(self) -> None:
        self.stop()
        self._widget = None

    def _schedule_tick(self) -> None:
        if not self._is_playing:
            return
        if self._root:
            try:
                self._timer_id = self._root.after(100, self._on_tick)
            except Exception:
                pass

    def _cancel_tick(self) -> None:
        if self._timer_id and self._root:
            try:
                self._root.after_cancel(self._timer_id)
            except Exception:
                pass
            self._timer_id = None

    def _on_tick(self) -> None:
        if not self._is_playing:
            return

        now = time.time()
        elapsed_ms = int((now - self._last_tick) * 1000)
        self._last_tick = now
        self._current_time_ms += elapsed_ms

        if self._current_time_ms >= self._duration_ms:
            if self._loop:
                self._current_time_ms = 0
                self._schedule_tick()
            else:
                self._is_playing = False
                self._current_time_ms = self._duration_ms
                if self._on_end:
                    self._on_end()
            return

        self._render_placeholder()
        self._schedule_tick()

    def _render_placeholder(self) -> None:
        """
        Optionally render mock status onto the widget canvas if supported.
        """
        if self._widget is None:
            return
        # If widget is a CTkCanvas or tk.Canvas, we can update text/progress
        try:
            if hasattr(self._widget, "delete") and hasattr(self._widget, "create_text"):
                self._widget.delete("mock_overlay")
                w = self._widget.winfo_width() or 360
                h = self._widget.winfo_height() or 400
                sec = self._current_time_ms / 1000.0
                total = self._duration_ms / 1000.0
                status = "▶ Playing" if self._is_playing else "⏸ Paused"
                text = f"{status}\n[Mock Video Player]\n{sec:.1f}s / {total:.1f}s"
                self._widget.create_text(
                    w // 2, h // 2,
                    text=text,
                    fill="#FFFFFF",
                    font=(UI_FONT, 12, "bold"),
                    tags="mock_overlay",
                    justify="center"
                )
        except Exception:
            pass


_shared_player_instance: Optional[BasePlayer] = None


def get_shared_player(root: Any = None) -> BasePlayer:
    """
    Singleton accessor for the application-wide shared player instance.
    Instantiates native SharedVlcPlayer if VLC is available, otherwise MockVlcPlayer.
    """
    global _shared_player_instance
    if _shared_player_instance is None:
        if _HAS_VLC:
            try:
                _shared_player_instance = SharedVlcPlayer(root=root)
                logger.info("Initialized native SharedVlcPlayer successfully.")
            except Exception as e:
                logger.warning("Failed to initialize native SharedVlcPlayer (%s); falling back to MockVlcPlayer.", e)
                _shared_player_instance = MockVlcPlayer(root=root)
        else:
            _shared_player_instance = MockVlcPlayer(root=root)
            logger.info("Initialized MockVlcPlayer.")
    elif root is not None and hasattr(_shared_player_instance, "set_root"):
        _shared_player_instance.set_root(root)
    return _shared_player_instance
