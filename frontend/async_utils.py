"""
Asynchronous worker pool and main-thread task queue dispatcher.
Ensures network calls and expensive image decodes run off the UI thread,
while all callbacks and UI widget manipulations execute strictly on the Tkinter main thread.
"""

from concurrent.futures import ThreadPoolExecutor
import logging
import queue
import sys
import threading
from typing import Any, Callable, Optional, Tuple

logger = logging.getLogger("SocialApp.async_utils")

# Worker pool configuration
DEFAULT_MAX_WORKERS = 4
_executor: Optional[ThreadPoolExecutor] = None
_task_queue: "queue.Queue[Tuple[str, Optional[Callable], Any]]" = queue.Queue()
_pump_active = False
_pump_after_id: Optional[str] = None
_lock = threading.Lock()


def get_executor() -> ThreadPoolExecutor:
    """Lazily initialize and return the global ThreadPoolExecutor."""
    global _executor
    with _lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(
                max_workers=DEFAULT_MAX_WORKERS,
                thread_name_prefix="SocialAppWorker"
            )
    return _executor


def run_async(
    fn: Callable[..., Any],
    *args: Any,
    on_success: Optional[Callable[[Any], None]] = None,
    on_error: Optional[Callable[[Exception], None]] = None,
    **kwargs: Any
) -> None:
    """
    Execute a callable asynchronously on the worker pool.
    Upon completion, dispatches on_success(result) or on_error(exc)
    to the main thread via the task queue.

    Tkinter widgets MUST NEVER be modified inside fn.
    All widget mutations belong in on_success or on_error.
    """
    executor = get_executor()

    def worker():
        try:
            result = fn(*args, **kwargs)
            if on_success:
                _task_queue.put(("success", on_success, result))
        except Exception as exc:
            logger.debug("Async worker exception in %s: %s", fn.__name__, exc)
            if on_error:
                _task_queue.put(("error", on_error, exc))
            else:
                # Default error logger if no error callback supplied
                logger.error("Unhandled async error in %s: %s", fn.__name__, exc, exc_info=True)

    executor.submit(worker)


def drain_queue() -> int:
    """
    Drain all currently queued tasks and execute their callbacks.
    MUST be called on the main/UI thread.
    Returns the number of tasks processed.
    """
    processed = 0
    while True:
        try:
            task_type, callback, payload = _task_queue.get_nowait()
        except queue.Empty:
            break

        processed += 1
        if callback is not None:
            try:
                callback(payload)
            except Exception as exc:
                logger.error(
                    "Error executing async callback for task_type=%s: %s",
                    task_type,
                    exc,
                    exc_info=True
                )
        _task_queue.task_done()
    return processed


def pump_queue(root: Any, interval_ms: int = 40) -> None:
    """
    Main-thread queue pump scheduled via root.after().
    Drains pending callbacks and reschedules itself.
    """
    global _pump_active, _pump_after_id
    if not _pump_active:
        return

    drain_queue()

    if _pump_active and root:
        try:
            _pump_after_id = root.after(interval_ms, lambda: pump_queue(root, interval_ms))
        except Exception:
            _pump_active = False


def start_queue_pump(root: Any, interval_ms: int = 40) -> None:
    """
    Start the continuous main-thread queue pump loop.
    """
    global _pump_active
    if _pump_active:
        return
    _pump_active = True
    if root:
        pump_queue(root, interval_ms)


def stop_queue_pump(root: Any = None) -> None:
    """
    Stop the main-thread queue pump loop.
    """
    global _pump_active, _pump_after_id
    _pump_active = False
    if root and _pump_after_id:
        try:
            root.after_cancel(_pump_after_id)
        except Exception:
            pass
        _pump_after_id = None


def shutdown_async(wait: bool = False) -> None:
    """
    Shut down the background worker pool and drain any remaining queue items.
    """
    global _executor, _pump_active
    _pump_active = False
    with _lock:
        if _executor is not None:
            _executor.shutdown(wait=wait, cancel_futures=True)
            _executor = None
