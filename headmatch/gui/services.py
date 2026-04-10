from __future__ import annotations

from dataclasses import dataclass
import queue
import threading
from pathlib import Path
from typing import Callable, Protocol

from ..utils import expanded_parent, expanded_dir


class FileDialogProtocol(Protocol):
    def askdirectory(self, **kwargs):
        pass

    def askopenfilename(self, **kwargs):
        pass

    def asksaveasfilename(self, **kwargs):
        pass


@dataclass(frozen=True)
class PickerOptions:
    title: str
    fallback: str | Path
    filetypes: tuple[tuple[str, str], ...] | None = None
    defaultextension: str | None = None
    mustexist: bool | None = None


class FilePickerService:
    """Service for file and directory selection dialogs.
    
    Provides a clean interface over tkinter.filedialog with
    centralized path expansion logic.
    """
    
    def __init__(self, filedialog: FileDialogProtocol | None, *, root=None):
        self._filedialog = filedialog
        self._root = root

    def choose_file(self, current_value: str, *, title: str, filetypes, fallback: str | Path) -> str | None:
        """Open file selection dialog.
        
        Args:
            current_value: Current file path (used to determine initial directory)
            title: Dialog title
            filetypes: File type filters for the dialog
            fallback: Default directory if current_value is empty
            
        Returns:
            Selected file path or None if cancelled
        """
        if self._filedialog is None:
            return None
        selected = self._filedialog.askopenfilename(
            title=title,
            initialdir=expanded_parent(current_value, fallback),
            parent=self._root,
            filetypes=filetypes,
        )
        return selected or None

    def choose_directory(self, current_value: str, *, title: str, fallback: str | Path) -> str | None:
        """Open directory selection dialog.
        
        Args:
            current_value: Current directory path
            title: Dialog title
            fallback: Default directory if current_value is empty
            
        Returns:
            Selected directory path or None if cancelled
        """
        if self._filedialog is None:
            return None
        selected = self._filedialog.askdirectory(
            title=title,
            initialdir=expanded_dir(current_value, fallback),
            parent=self._root,
            mustexist=False,
        )
        return selected or None

    def choose_save_file(self, current_value: str, *, title: str, filetypes, fallback: str | Path, defaultextension: str | None = None) -> str | None:
        """Open save file dialog.
        
        Args:
            current_value: Current file path (used to determine initial directory)
            title: Dialog title
            filetypes: File type filters for the dialog
            fallback: Default directory if current_value is empty
            defaultextension: Default file extension
            
        Returns:
            Selected file path or None if cancelled
        """
        if self._filedialog is None:
            return None
        selected = self._filedialog.asksaveasfilename(
            title=title,
            initialdir=expanded_parent(current_value, fallback),
            parent=self._root,
            filetypes=filetypes,
            defaultextension=defaultextension,
        )
        return selected or None


@dataclass
class BackgroundTaskResult:
    event: str
    payload: object


class BackgroundTaskService:
    """Service for running background tasks with queue-based completion.
    
    Executes work in a background thread and posts results to a queue
    for the main thread to poll.
    """
    
    def __init__(self, *, task_queue: queue.Queue[tuple[str, object]] | None = None, thread_factory: Callable[..., threading.Thread] = threading.Thread):
        self._task_queue = task_queue or queue.Queue()
        self._thread_factory = thread_factory

    @property
    def task_queue(self):
        return self._task_queue

    def start(self, worker: Callable[[], object]) -> None:
        """Start a background task.
        
        Args:
            worker: Callable to execute in background thread.
                    Results are posted as ("success", result) to the queue.
                    Exceptions are posted as ("error", exception).
        """
        def target() -> None:
            try:
                result = worker()
            except Exception as exc:
                self._task_queue.put(("error", exc))
                return
            self._task_queue.put(("success", result))

        self._thread_factory(target=target, daemon=True).start()
