from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from headmatch.gui.controllers import WorkflowControllers


class DummyVar:
    def __init__(self, value=""):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value


class DummyChild:
    def destroy(self):
        return None


def make_app(tmp_path):
    content = SimpleNamespace(winfo_children=lambda: [DummyChild()])
    app = SimpleNamespace(
        history_root_var=DummyVar(str(tmp_path / "history")),
        state=SimpleNamespace(config_path=tmp_path / "config.json", mode="advanced", sample_rate=48000, duration_s=2.0, f_start_hz=20.0, f_end_hz=20000.0, pre_silence_s=0.2, post_silence_s=0.5, amplitude=0.7),
        output_dir_var=DummyVar(str(tmp_path / "out")),
        target_csv_var=DummyVar(""),
        output_target_var=DummyVar("dev1 — Speaker"),
        input_target_var=DummyVar("dev2 — Mic"),
        iterations_var=DummyVar("3"),
        max_filters_var=DummyVar("10"),
        mode_var=DummyVar("advanced"),
        doctor_report_var=DummyVar(""),
        current_view=DummyVar("setup-check"),
        content=content,
        _render_setup_check=lambda: setattr(app, "rendered_setup", True),
        _doctor_report_runner=None,
        _strip_device_label=lambda s: s.split(" — ", 1)[0],
        _parse_positive_int=lambda s, _label: int(s),
        _show_status=lambda msg: setattr(app, "status", msg),
        _ttk=SimpleNamespace(Label=lambda *a, **k: SimpleNamespace(grid=lambda *a, **k: None), Scrollbar=lambda *a, **k: SimpleNamespace(grid=lambda *a, **k: None)),
        _search_results_frame=SimpleNamespace(winfo_children=lambda: []),
        _on_search_result_selected=lambda *_a, **_k: None,
        apo_preset_var=DummyVar(""),
        apo_refine_recording_var=DummyVar(""),
        apo_refine_output_var=DummyVar(str(tmp_path / "refined")),
        apo_refine_target_var=DummyVar(""),
        apo_output_dir_var=DummyVar(str(tmp_path / "imported")),
        fetch_search_var=DummyVar(""),
        fetch_url_var=DummyVar(""),
        fetch_output_var=DummyVar(""),
        basic_clone_source_var=DummyVar(""),
        basic_clone_target_var=DummyVar(""),
        basic_clone_output_var=DummyVar(""),
        basic_target_csv_var=DummyVar(""),
        basic_target_mode_var=DummyVar("flat"),
        _run_background_task=lambda **kwargs: setattr(app, "last_task", kwargs),
        _set_completion=lambda **kwargs: setattr(app, "completion", kwargs),
        _build_sweep=lambda: "sweep",
        _online_runner=lambda **kwargs: kwargs,
        _offline_fit_runner=lambda *args, **kwargs: {"ok": True},
        offline_recording_var=DummyVar(str(tmp_path / "recording.wav")),
        offline_fit_output_var=DummyVar(str(tmp_path / "fit")),
        iteration_mode_var=DummyVar("independent"),
        offine_notes_var=DummyVar(""),
        offline_notes_var=DummyVar(""),
    )
    return app


def test_refresh_setup_check_updates_report_and_rerenders(tmp_path):
    app = make_app(tmp_path)
    app._doctor_report_runner = lambda path, config: f"report:{path.name}:{config.pipewire_output_target}:{config.pipewire_input_target}"
    controllers = WorkflowControllers(app)

    controllers.refresh_setup_check()

    assert app.doctor_report_var.get().startswith("report:config.json:dev1:dev2")
    assert app.rendered_setup is True


def test_run_apo_import_requires_paths(tmp_path):
    app = make_app(tmp_path)
    controllers = WorkflowControllers(app)

    controllers.run_apo_import()

    assert "select both" in app.status.lower()


def test_run_search_headphone_requires_query(tmp_path):
    app = make_app(tmp_path)
    controllers = WorkflowControllers(app)

    controllers.run_search_headphone()

    assert "enter a headphone model" in app.status.lower()


def test_start_basic_clone_target_requires_all_paths(tmp_path):
    app = make_app(tmp_path)
    controllers = WorkflowControllers(app)

    with pytest.raises(ValueError, match="required"):
        controllers.start_basic_clone_target()


def test_start_basic_measurement_uses_average_mode(tmp_path, monkeypatch):
    app = make_app(tmp_path)
    app.basic_target_mode_var.set("database")
    app.basic_target_csv_var.set(str(tmp_path / "target.csv"))
    monkeypatch.setattr("headmatch.gui.controllers.iterative_measure_and_fit", lambda **kwargs: kwargs)
    controllers = WorkflowControllers(app)

    controllers.start_basic_measurement()

    task = app.last_task
    assert task["task_name"] == "basic-mode"
    result = task["worker"]()
    assert result["iterations"] == 3
    assert result["iteration_mode"] == "average"
    assert result["target_path"] == str(tmp_path / "target.csv")
    assert result["output_target"] is None
    assert result["input_target"] is None


def test_save_current_config_persists_mode_and_stripped_targets(tmp_path, monkeypatch):
    app = make_app(tmp_path)
    seen = {}
    monkeypatch.setattr("headmatch.gui.controllers.save_config", lambda config, path: seen.update({"config": config, "path": path}))
    controllers = WorkflowControllers(app)

    controllers.save_current_config()

    assert seen["path"] == tmp_path / "config.json"
    assert seen["config"].pipewire_output_target == "dev1"
    assert seen["config"].pipewire_input_target == "dev2"
    assert seen["config"].mode == "advanced"
