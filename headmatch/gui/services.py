from __future__ import annotations

from dataclasses import dataclass
import queue
import threading
from pathlib import Path
from typing import Callable, Protocol


class FileDialogProtocol(Protocol):
    def askdirectory(self, **kwargs): ...
    def askopenfilename(self, **kwargs): ...
    def asksaveasfilename(self, **kwargs): ...


@dataclass(frozen=True)
class PickerOptions:
    title: str
    fallback: str | Path
    filetypes: tuple[tuple[str, str], ...] | None = None
    defaultextension: str | None = None
    mustexist: bool | None = None


class FilePickerService:
    def __init__(self, filedialog: FileDialogProtocol | None, *, root=None):
        self._filedialog = filedialog
        self._root = root

    @staticmethod
    def _expanded_parent(value: str, fallback: str | Path) -> str:
        raw = value.strip()
        if raw:
            return str(Path(raw).expanduser().parent)
        return str(Path(fallback).expanduser())

    @staticmethod
    def _expanded_dir(value: str, fallback: str | Path) -> str:
        raw = value.strip()
        if raw:
            return str(Path(raw).expanduser())
        return str(Path(fallback).expanduser())

    def choose_file(self, current_value: str, *, title: str, filetypes, fallback: str | Path) -> str | None:
        if self._filedialog is None:
            return None
        selected = self._filedialog.askopenfilename(
            title=title,
            initialdir=self._expanded_parent(current_value, fallback),
            parent=self._root,
            filetypes=filetypes,
        )
        return selected or None

    def choose_directory(self, current_value: str, *, title: str, fallback: str | Path) -> str | None:
        if self._filedialog is None:
            return None
        selected = self._filedialog.askdirectory(
            title=title,
            initialdir=self._expanded_dir(current_value, fallback),
            parent=self._root,
            mustexist=False,
        )
        return selected or None

    def choose_save_file(self, current_value: str, *, title: str, filetypes, fallback: str | Path, defaultextension: str | None = None) -> str | None:
        if self._filedialog is None:
            return None
        selected = self._filedialog.asksaveasfilename(
            title=title,
            initialdir=self._expanded_parent(current_value, fallback),
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
    def __init__(self, *, task_queue: queue.Queue[tuple[str, object]] | None = None, thread_factory: Callable[..., threading.Thread] = threading.Thread):
        self._task_queue = task_queue or queue.Queue()
        self._thread_factory = thread_factory

    @property
    def task_queue(self):
        return self._task_queue

    def start(self, worker: Callable[[], object]) -> None:
        def target() -> None:
            try:
                result = worker()
            except Exception as exc:  # pragma: no cover
                self._task_queue.put(("error", exc))
                return
            self._task_queue.put(("success", result))

        self._thread_factory(target=target, daemon=True).start()
