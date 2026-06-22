"""Progress tracking for long-running operations.

Provides a thread-safe ProgressTracker singleton that can be polled
via SSE (Server-Sent Events) for real-time progress updates.
"""

import asyncio
import threading
from typing import Any

from key_manager.api_models import ProgressResponse

# Global progress tracker

class ProgressTracker:
    """Thread-safe progress tracker for long-running operations."""

    def __init__(self):
        self._lock = threading.Lock()
        self._active = False
        self._current = 0
        self._total = 0
        self._status = ""
        self._results: dict[str, Any] | None = None

    def start(self, total: int, status: str = "loading"):
        with self._lock:
            self._active = True
            self._current = 0
            self._total = total
            self._status = status
            self._results = None

    def update(self, current: int, total: int):
        with self._lock:
            self._current = current
            self._total = total

    def done(self, status: str = "done", results: dict[str, Any] | None = None):
        with self._lock:
            self._active = False
            self._current = self._total
            self._status = status
            self._results = results

    def snapshot(self) -> ProgressResponse:
        with self._lock:
            return ProgressResponse(
                active=self._active,
                current=self._current,
                total=self._total,
                status=self._status,
                results=self._results,
            )


_progress_tracker = ProgressTracker()


def _make_progress_callback():
    """Return a (current, total) callable that updates the global tracker."""
    def cb(current: int, total: int):
        _progress_tracker.update(current, total)
    return cb


# SSE helpers

async def _sse_progress_event_generator(poll_interval: float = 0.5):
    """SSE generator that polls the progress tracker until the task completes."""
    while True:
        snap = _progress_tracker.snapshot()
        data = snap.model_dump_json()
        yield f"data: {data}\n\n"
        if not snap.active:
            yield "data: [DONE]\n\n"
            break
        await asyncio.sleep(poll_interval)
