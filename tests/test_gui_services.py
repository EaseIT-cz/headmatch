from __future__ import annotations

import queue
from pathlib import Path

from headmatch.gui.services import BackgroundTaskService, FilePickerService


class DummyDialog:
    def __init__(self):
        self.calls = []
        self.open_result = ""
        self.dir_result = ""
        self.save_result = ""

    def askopenfilename(self, **kwargs):
        self.calls.append(("open", kwargs))
        return self.open_result

    def askdirectory(self, **kwargs):
        self.calls.append(("dir", kwargs))
        return self.dir_result

    def asksaveasfilename(self, **kwargs):
        self.calls.append(("save", kwargs))
        return self.save_result


class ImmediateThread:
    def __init__(self, *, target, daemon):
        self.target = target
        self.daemon = daemon

    def start(self):
        self.target()


def test_file_picker_service_uses_parent_dir_for_files(tmp_path):
    dialog = DummyDialog()
    dialog.open_result = str(tmp_path / "picked.csv")
    service = FilePickerService(dialog)

    selected = service.choose_file(str(tmp_path / "sub" / "current.csv"), title="Choose", filetypes=(("CSV", "*.csv"),), fallback=tmp_path)

    assert selected == str(tmp_path / "picked.csv")
    kind, kwargs = dialog.calls[0]
    assert kind == "open"
    assert kwargs["initialdir"] == str((tmp_path / "sub").expanduser())


def test_file_picker_service_uses_fallback_for_empty_value(tmp_path):
    dialog = DummyDialog()
    dialog.dir_result = str(tmp_path / "out")
    service = FilePickerService(dialog)

    selected = service.choose_directory("", title="Choose dir", fallback=tmp_path / "fallback")

    assert selected == str(tmp_path / "out")
    kind, kwargs = dialog.calls[0]
    assert kind == "dir"
    assert kwargs["initialdir"] == str((tmp_path / "fallback").expanduser())


def test_file_picker_service_returns_none_when_dialog_missing(tmp_path):
    service = FilePickerService(None)
    assert service.choose_file("", title="x", filetypes=(("CSV", "*.csv"),), fallback=tmp_path) is None
    assert service.choose_directory("", title="x", fallback=tmp_path) is None
    assert service.choose_save_file("", title="x", filetypes=(("CSV", "*.csv"),), fallback=tmp_path) is None


def test_background_task_service_success_puts_success_event():
    q = queue.Queue()
    service = BackgroundTaskService(task_queue=q, thread_factory=ImmediateThread)

    service.start(lambda: 123)

    event, payload = q.get_nowait()
    assert event == "success"
    assert payload == 123


def test_background_task_service_error_puts_error_event():
    q = queue.Queue()
    service = BackgroundTaskService(task_queue=q, thread_factory=ImmediateThread)

    def boom():
        raise RuntimeError("boom")

    service.start(boom)

    event, payload = q.get_nowait()
    assert event == "error"
    assert isinstance(payload, RuntimeError)
    assert str(payload) == "boom"
