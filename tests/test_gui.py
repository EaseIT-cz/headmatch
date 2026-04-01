from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from headmatch.contracts import FrontendConfig
from headmatch.gui import NAV_ITEMS, build_arg_parser, load_gui_state, main


class DummyVar:
    def __init__(self, master=None, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class DummyWidget:
    def __init__(self, *args, **kwargs):
        self.command = kwargs.get("command")

    def grid(self, *args, **kwargs):
        return self

    def columnconfigure(self, *args, **kwargs):
        return None

    def rowconfigure(self, *args, **kwargs):
        return None

    def state(self, *_args, **_kwargs):
        return None

    def winfo_children(self):
        return []

    def destroy(self):
        return None


class DummyRoot(DummyWidget):
    def __init__(self):
        super().__init__()
        self.title_value = None
        self.minsize_value = None

    def title(self, value):
        self.title_value = value

    def minsize(self, w, h):
        self.minsize_value = (w, h)

    def after(self, _delay, callback):
        callback()

    def mainloop(self):
        return None


class DummyTtk:
    Frame = DummyWidget
    Label = DummyWidget
    Button = DummyWidget
    LabelFrame = DummyWidget
    Entry = DummyWidget


@pytest.fixture
def fake_tk(monkeypatch):
    import headmatch.gui as gui

    monkeypatch.setitem(sys.modules, 'tkinter', SimpleNamespace(StringVar=DummyVar, ttk=DummyTtk))
    monkeypatch.setitem(sys.modules, 'tkinter.ttk', DummyTtk)
    return gui


def test_load_gui_state_preloads_saved_config_values(tmp_path):
    config = FrontendConfig(
        default_output_dir="saved/session",
        preferred_target_csv="targets/custom.csv",
        pipewire_output_target="speakers",
        pipewire_input_target="in-ear-mic",
        start_iterations=3,
        max_filters=6,
    )

    state = load_gui_state(config_loader=lambda _path=None: (config, tmp_path / "config.json", False))

    assert state.version_display == "0.2.0"
    assert state.current_view == "home"
    assert state.default_output_dir == "saved/session"
    assert state.preferred_target_csv == "targets/custom.csv"
    assert state.pipewire_output_target == "speakers"
    assert state.pipewire_input_target == "in-ear-mic"
    assert state.start_iterations == 3
    assert state.max_filters == 6
    assert state.sample_rate == 48000



def test_load_gui_state_uses_safe_defaults_when_config_is_empty(tmp_path):
    state = load_gui_state(config_loader=lambda _path=None: (FrontendConfig(), tmp_path / "config.json", True))

    assert state.default_output_dir == "out/session_01"
    assert state.preferred_target_csv == ""
    assert state.pipewire_output_target == ""
    assert state.pipewire_input_target == ""
    assert state.config_created is True



def test_navigation_items_cover_shell_sections():
    assert [item.key for item in NAV_ITEMS] == [
        "home",
        "measure-online",
        "prepare-offline",
        "history",
    ]
    history_item = next(item for item in NAV_ITEMS if item.key == "history")
    assert "Browse recent runs" in history_item.description



def test_gui_main_reports_tcl_startup_errors(monkeypatch):
    monkeypatch.setattr("headmatch.gui.create_app", lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    with pytest.raises(RuntimeError):
        main([])

    class FakeTclError(Exception):
        pass

    FakeTclError.__name__ = "TclError"
    monkeypatch.setattr("headmatch.gui.create_app", lambda **_kwargs: (_ for _ in ()).throw(FakeTclError("no display")))

    with pytest.raises(SystemExit) as exc:
        main([])

    assert str(exc.value) == "GUI could not start: no display"



def test_gui_arg_parser_accepts_config_override():
    parser = build_arg_parser()
    args = parser.parse_args(["--config", str(Path("custom.json"))])
    assert args.config == "custom.json"



def test_gui_history_selection_reads_recent_runs(tmp_path):
    run_dir = tmp_path / "session_01"
    run_dir.mkdir()
    guide = run_dir / "README.txt"
    guide.write_text("headmatch fit results\n")
    summary = run_dir / "run_summary.json"
    summary.write_text(
        """{
  "kind": "fit",
  "out_dir": "%s",
  "sample_rate": 48000,
  "frequency_points": 512,
  "target": "flat",
  "filters": {"left": 4, "right": 4},
  "predicted_error_db": {"left_rms": 1.0, "right_rms": 1.1, "left_max": 3.0, "right_max": 3.1},
  "results_guide": "%s"
}
""" % (run_dir, guide)
    )

    state = load_gui_state(config_loader=lambda _path=None: (FrontendConfig(default_output_dir=str(tmp_path / "out" / "session_01")), tmp_path / "config.json", False))
    app = object.__new__(__import__("headmatch.gui", fromlist=["HeadMatchGuiApp"]).HeadMatchGuiApp)
    app.state = state

    class DummyHistoryVar:
        def __init__(self, value):
            self.value = value

        def get(self):
            return self.value

    app.history_root_var = DummyHistoryVar(str(tmp_path))

    selection = app.build_history_selection()

    assert selection.search_root == str(tmp_path)
    assert selection.selected_summary == str(summary)
    assert "headmatch fit results" in selection.selected_guide
    assert selection.items[0][0] == str(run_dir)



def test_create_app_builds_shell_on_fake_root(tmp_path, fake_tk):
    root = DummyRoot()
    app = fake_tk.create_app(
        root=root,
        config_loader=lambda _path=None: (FrontendConfig(default_output_dir=str(tmp_path / 'out' / 'session_01')), tmp_path / 'config.json', False),
    )

    assert root.title_value == 'HeadMatch 0.2.0'
    assert root.minsize_value == (920, 580)
    assert app.history_root_var.get() == str(tmp_path / 'out')
    assert app.offline_fit_output_var.get().endswith('fit')



def test_online_workflow_uses_shared_pipeline_and_sets_completion(tmp_path, fake_tk, monkeypatch):
    calls = {}

    class ImmediateThread:
        def __init__(self, *, target, daemon):
            self.target = target

        def start(self):
            self.target()

    monkeypatch.setattr(fake_tk.threading, 'Thread', ImmediateThread)

    root = DummyRoot()
    app = fake_tk.create_app(
        root=root,
        config_loader=lambda _path=None: (FrontendConfig(default_output_dir=str(tmp_path / 'session_01'), start_iterations=2, max_filters=5), tmp_path / 'config.json', False),
        online_runner=lambda **kwargs: calls.update(kwargs) or [],
    )

    app.iterations_var.set('2')
    app.max_filters_var.set('5')
    app.start_online_measurement()

    assert calls['output_dir'] == str(tmp_path / 'session_01')
    assert calls['iterations'] == 2
    assert calls['max_filters'] == 5
    assert app.completion_title_var.get() == 'Online measurement complete'
    assert 'run_summary.json' in app._last_completion_steps[1]



def test_offline_prepare_workflow_writes_package_plan(tmp_path, fake_tk, monkeypatch):
    calls = {}

    class ImmediateThread:
        def __init__(self, *, target, daemon):
            self.target = target

        def start(self):
            self.target()

    monkeypatch.setattr(fake_tk.threading, 'Thread', ImmediateThread)

    root = DummyRoot()
    app = fake_tk.create_app(
        root=root,
        config_loader=lambda _path=None: (FrontendConfig(default_output_dir=str(tmp_path / 'offline')), tmp_path / 'config.json', False),
        offline_prepare_runner=lambda spec, plan: calls.update({'spec': spec, 'plan': plan}) or {'ok': True},
    )

    app.offline_notes_var.set('bring recorder')
    app.start_offline_prepare()

    assert calls['plan'].sweep_wav == tmp_path / 'offline' / 'sweep.wav'
    assert calls['plan'].metadata_json == tmp_path / 'offline' / 'measurement_plan.json'
    assert calls['plan'].notes == 'bring recorder'
    assert app.completion_title_var.get() == 'Offline package ready'



def test_offline_fit_workflow_uses_shared_pipeline(tmp_path, fake_tk, monkeypatch):
    calls = {}

    class ImmediateThread:
        def __init__(self, *, target, daemon):
            self.target = target

        def start(self):
            self.target()

    monkeypatch.setattr(fake_tk.threading, 'Thread', ImmediateThread)

    recording = tmp_path / 'recording.wav'
    recording.write_bytes(b'fake')

    root = DummyRoot()
    app = fake_tk.create_app(
        root=root,
        config_loader=lambda _path=None: (FrontendConfig(default_output_dir=str(tmp_path / 'offline'), max_filters=4), tmp_path / 'config.json', False),
        offline_fit_runner=lambda recording_wav, out_dir, sweep_spec, **kwargs: calls.update({'recording': recording_wav, 'out_dir': out_dir, 'kwargs': kwargs}) or {'ok': True},
    )

    app.offline_recording_var.set(str(recording))
    app.offline_fit_output_var.set(str(tmp_path / 'offline-fit'))
    app.start_offline_fit()

    assert calls['recording'] == str(recording)
    assert calls['out_dir'] == str(tmp_path / 'offline-fit')
    assert calls['kwargs']['max_filters'] == 4
    assert app.completion_title_var.get() == 'Offline fit complete'
