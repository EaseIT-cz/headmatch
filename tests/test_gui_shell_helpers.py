from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from headmatch.gui.shell import HeadMatchGuiApp, NavigationItem
from headmatch.headphone_db import HeadphoneEntry
from tests.test_gui import DummyVar


def test_resolve_device_display_prefers_labeled_option():
    options = ("12 — USB DAC", "13 — Mic")
    assert HeadMatchGuiApp._resolve_device_display("12", options) == "12 — USB DAC"
    assert HeadMatchGuiApp._resolve_device_display("99", options) == "99"


def test_strip_device_label_returns_bare_id():
    assert HeadMatchGuiApp._strip_device_label("12 — USB DAC") == "12"
    assert HeadMatchGuiApp._strip_device_label("plain") == "plain"


def test_parse_positive_int_validates_input():
    app = SimpleNamespace()
    assert HeadMatchGuiApp._parse_positive_int(app, "3", "Iterations") == 3
    with pytest.raises(ValueError, match="whole number"):
        HeadMatchGuiApp._parse_positive_int(app, "x", "Iterations")
    with pytest.raises(ValueError, match="greater than 0"):
        HeadMatchGuiApp._parse_positive_int(app, "0", "Iterations")


def test_refresh_basic_mode_target_step_only_rerenders_target_view():
    called = []
    app = SimpleNamespace(current_view=DummyVar(value="basic-mode"), basic_step_var=DummyVar(value="target"), show_view=lambda key: called.append(key))
    HeadMatchGuiApp.refresh_basic_mode_target_step(app)
    assert called == ["basic-mode"]

    called.clear()
    app.basic_step_var.set("measure")
    HeadMatchGuiApp.refresh_basic_mode_target_step(app)
    assert called == []


def test_choose_basic_search_match_rejects_invalid_index():
    app = SimpleNamespace(basic_search_matches=[], basic_search_results_var=DummyVar(value=""))
    HeadMatchGuiApp.choose_basic_search_match(app, 0)
    assert "Invalid" in app.basic_search_results_var.get()


def test_choose_basic_search_match_downloads_selection(monkeypatch, tmp_path):
    calls = {}
    monkeypatch.setattr("headmatch.paths.documents_dir", lambda: tmp_path)
    monkeypatch.setattr("headmatch.gui.shell.fetch_curve_from_url", lambda url, out_path: calls.update({"url": url, "out": Path(out_path)}) or Path(out_path))
    refreshed = []
    app = SimpleNamespace(
        basic_search_matches=[HeadphoneEntry(name="HD 650", source="oratory1990", form_factor="over-ear", csv_path="results/oratory1990/over-ear/HD 650/HD 650.csv")],
        basic_search_results_var=DummyVar(value=""),
        basic_target_mode_var=DummyVar(value="flat"),
        basic_target_csv_var=DummyVar(value=""),
        basic_target_path_var=DummyVar(value=""),
        basic_search_choice_var=DummyVar(value=""),
        refresh_basic_mode_target_step=lambda: refreshed.append(True),
    )

    HeadMatchGuiApp.choose_basic_search_match(app, 0)

    assert calls["url"].startswith("https://")
    assert app.basic_target_mode_var.get() == "database"
    assert app.basic_target_csv_var.get().endswith("HD 650 - oratory1990.csv")
    assert app.basic_search_choice_var.get() == "HD 650 — oratory1990"
    assert refreshed == [True]


def test_choose_target_csv_sets_basic_mode_state():
    app = SimpleNamespace(
        basic_search_results_var=DummyVar(value="old"),
        target_csv_var=DummyVar(value="/tmp/target.csv"),
        state=SimpleNamespace(config_path=Path("/tmp/config.json")),
        basic_target_csv_var=DummyVar(value=""),
        basic_target_path_var=DummyVar(value=""),
        basic_target_mode_var=DummyVar(value="flat"),
        refresh_basic_mode_target_step=lambda: None,
        _choose_file=lambda variable, **kwargs: None,
    )

    HeadMatchGuiApp.choose_target_csv(app)

    assert app.basic_search_results_var.get() == ""
    assert app.basic_target_csv_var.get() == "/tmp/target.csv"
    assert app.basic_target_path_var.get() == "/tmp/target.csv"
    assert app.basic_target_mode_var.get() == "csv"


def test_nav_items_for_mode_switches_between_basic_and_advanced():
    app = SimpleNamespace(mode_var=DummyVar(value="basic"))
    items = HeadMatchGuiApp._nav_items_for_mode(app)
    assert items[0].key == "basic-mode"

    app.mode_var.set("advanced")
    items = HeadMatchGuiApp._nav_items_for_mode(app)
    assert items[0].key == "measure-online"


def test_run_background_task_sets_progress_and_enqueues_success():
    class BG:
        def start(self, worker):
            self.payload = worker()
    app = SimpleNamespace(
        _active_task_name=None,
        progress_title_var=DummyVar(value=""),
        progress_body_var=DummyVar(value=""),
        show_view_progress=lambda: setattr(app, "showed", True),
        _background_tasks=BG(),
        _schedule_task_poll=lambda: setattr(app, "scheduled", True),
    )

    HeadMatchGuiApp._run_background_task(app, task_name="x", progress_title="Title", progress_body="Body", worker=lambda: 123, on_success=lambda result: result)

    assert app._active_task_name == "x"
    assert app.progress_title_var.get() == "Title"
    assert app.progress_body_var.get() == "Body"
    assert app.showed is True
    assert app.scheduled is True
    assert app._background_tasks.payload[1] == 123


def test_run_background_task_rejects_parallel_work():
    app = SimpleNamespace(_active_task_name="busy")
    with pytest.raises(RuntimeError, match="already running"):
        HeadMatchGuiApp._run_background_task(app, task_name="x", progress_title="t", progress_body="b", worker=lambda: None, on_success=lambda r: None)


def test_poll_task_queue_handles_error_and_success():
    class Q:
        def __init__(self, items):
            self.items = items
        def get_nowait(self):
            if not self.items:
                import queue
                raise queue.Empty
            return self.items.pop(0)
    completions = []
    app = SimpleNamespace(
        _task_queue=Q([("error", RuntimeError("boom"))]),
        _active_task_name="x",
        _set_completion=lambda **kwargs: completions.append(kwargs),
        root=SimpleNamespace(after=lambda *_a, **_k: None),
    )
    HeadMatchGuiApp._poll_task_queue(app)
    assert app._active_task_name is None
    assert completions[0]["title"] == "Workflow could not finish"

    done = []
    app = SimpleNamespace(
        _task_queue=Q([("success", (lambda result: done.append(result), 42))]),
        _active_task_name="x",
    )
    HeadMatchGuiApp._poll_task_queue(app)
    assert done == [42]


def test_poll_task_queue_reschedules_when_empty():
    import queue
    class Q:
        def get_nowait(self):
            raise queue.Empty
    called = []
    app = SimpleNamespace(_task_queue=Q(), _active_task_name="x")
    app.root = SimpleNamespace(after=lambda delay, cb: called.append((delay, cb)))
    app._poll_task_queue = lambda: None
    HeadMatchGuiApp._poll_task_queue(app)
    assert called and called[0][0] == 100


def test_set_completion_updates_state_and_renders():
    destroyed = []
    app = SimpleNamespace(
        _last_completion_steps=(),
        _completion_clipping_assessment=None,
        completion_title_var=DummyVar(value=""),
        completion_body_var=DummyVar(value=""),
        _save_current_config=lambda: destroyed.append("saved"),
        content=SimpleNamespace(winfo_children=lambda: [SimpleNamespace(destroy=lambda: destroyed.append("destroyed"))]),
        _render_completion=lambda: destroyed.append("rendered"),
    )
    HeadMatchGuiApp._set_completion(app, title="Done", summary="ok", steps=("a",), result={"eq_clipping": {"risk": "high"}})
    assert app.completion_title_var.get() == "Done"
    assert app.completion_body_var.get() == "ok"
    assert app._completion_clipping_assessment == {"risk": "high"}
    assert destroyed == ["saved", "destroyed", "rendered"]
