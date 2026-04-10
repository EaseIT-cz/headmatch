"""Background task utilities for GUI and testing.

Provides test doubles and helpers for background task operations.
"""

from __future__ import annotations

import queue
from typing import Any, Callable


class ImmediateThread:
    """Test double for threading.Thread that runs synchronously.
    
    Used in tests to execute background tasks immediately instead
    of spawning actual threads. This makes tests deterministic
    and avoids race conditions.
    
    Example:
        >>> service = BackgroundTaskService(
        ...     task_queue=queue.Queue(),
        ...     thread_factory=ImmediateThread
        ... )
        >>> service.start(lambda: 42)  # Runs immediately
        >>> event, payload = service.task_queue.get_nowait()
        >>> assert event == "success"
        >>> assert payload == 42
    """
    
    def __init__(self, *, target: Callable[[], Any], daemon: bool):
        """Initialize immediate thread.
        
        Args:
            target: Function to execute
            daemon: Ignored (for API compatibility)
        """
        self.target = target
        self.daemon = daemon
    
    def start(self) -> None:
        """Execute target immediately."""
        self.target()


class SyncQueue:
    """Synchronous queue wrapper for deterministic testing.
    
    Wraps a queue.Queue with helper methods for test assertions.
    
    Example:
        >>> q = SyncQueue()
        >>> q.put(("success", 123))
        >>> assert q.get_event() == "success"
        >>> assert q.get_payload() == 123
    """
    
    def __init__(self, items: list | None = None):
        """Initialize queue with optional pre-populated items.
        
        Args:
            items: Optional list of (event, payload) tuples
        """
        self._queue: queue.Queue = queue.Queue()
        self._last_event: str | None = None
        self._last_payload: Any = None
        
        if items:
            for item in items:
                self._queue.put(item)
    
    def put(self, item: tuple[str, Any]) -> None:
        """Add item to queue."""
        self._queue.put(item)
    
    def get_nowait(self) -> tuple[str, Any]:
        """Get item from queue, raising Empty if empty."""
        return self._queue.get_nowait()
    
    def get_event(self) -> str:
        """Get current event type, consuming from queue."""
        event, payload = self.get_nowait()
        self._last_event = event
        self._last_payload = payload
        return event
    
    def get_payload(self) -> Any:
        """Return last payload after get_event() call."""
        return self._last_payload
    
    def is_empty(self) -> bool:
        """Check if queue is empty."""
        try:
            self._queue.get_nowait()
            return False
        except queue.Empty:
            return True
