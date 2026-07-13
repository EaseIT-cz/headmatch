"""Centralized background task helpers for threading."""
from __future__ import annotations

import threading
from typing import Any, Callable


def _worker(
    func: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    on_error: Callable[[BaseException], None] | None = None,
    on_success: Callable[[Any], None] | None = None,
) -> Any:
    """Worker function that executes func and handles errors.
    
    Args:
        func: Function to execute
        args: Positional arguments for func
        kwargs: Keyword arguments for func
        on_error: Optional callback for exceptions
        on_success: Optional callback for successful results
        
    Returns:
        Result of func execution
    """
    try:
        result = func(*args, **kwargs)
        if on_success is not None:
            on_success(result)
        return result
    except BaseException as exc:
        if on_error is not None:
            on_error(exc)
        return None


def run_in_thread(
    func: Callable[..., Any],
    *args: Any,
    daemon: bool = True,
    on_error: Callable[[BaseException], None] | None = None,
    on_success: Callable[[Any], None] | None = None,
    **kwargs: Any,
) -> threading.Thread:
    """Run a function in a background thread.
    
    Args:
        func: Function to execute in background
        *args: Positional arguments for func
        daemon: Whether thread should be daemon (default: True)
        on_error: Optional callback for exceptions
        on_success: Optional callback for successful results
        **kwargs: Keyword arguments for func
        
    Returns:
        The started Thread instance
    """
    # Create a wrapper that will call _worker with the correct args
    def target() -> Any:
        return _worker(func, args, kwargs, on_error=on_error, on_success=on_success)
    
    thread = threading.Thread(
        target=target,
        daemon=daemon,
    )
    thread.start()
    return thread