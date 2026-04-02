from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import sys

import pytest

from headmatch.contracts import FrontendConfig
from headmatch.gui import NAV_ITEMS, build_arg_parser, build_doctor_report, load_gui_state, main
from headmatch.measure import PipeWireTargetSelection
from headmatch.settings import save_config


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
        self.kwargs = kwargs

    def grid(self, *args, **kwargs):
        return self

    def grid_propagate(self, *args, **kwargs):
        return None

    def columnconfigure(self, *args, **kwargs):
        return None

    def rowconfigure(self, *args, **kwargs):
        return None

    def state(self, *_args, **_kwargs):
        return None

    def configure(self, *args, **kwargs):
        return None

    config = configure

    def bind(self, *args, **kwargs):
        return None

    def set(self, *args, **kwargs):
        return None

    def yview(self, *args, **kwargs):
        return None

    def create_window(self, *args, **kwargs):
        return 1

    def itemconfigure(self, *args, **kwargs):
        return None

    def bbox(self, *args, **kwargs):
        return (0, 0, 640, 480)

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
    Scrollbar = DummyWidget
    Combobox = DummyWidget


class DummyStyle:
    def __init__(self, *_args, **_kwargs):
        self.current_theme = "default"

    def theme_use(self, theme=None):
        if theme is not None:
            self.current_theme = theme
        return self.current_theme

    def configure(self, *_args, **_kwargs):
        return None


DummyTtk.Style = DummyStyle


@pytest.fixture
def fake_tk(monkeypatch):
    import headmatch.gui as gui

    monkeypatch.setitem(sys.modules, 'tkinter', SimpleNamespace(StringVar=DummyVar, ttk=DummyTtk, Canvas=DummyWidget))
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
    assert state.current_view == "measure-online"
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
        "measure-online",
        "setup-check",
        "launch-help",
        "prepare-offline",
        "history",
    ]
    assert [item.label for item in NAV_ITEMS] == ["Measure", "Setup Check", "Launch Help", "Prepare Offline", "Results"]



def test_online_steps_explain_playback_vs_capture_targets():
    from headmatch import gui_views

    assert any("Playback target = the DAC, headphones, speakers, or interface output" in step for step in gui_views.ONLINE_STEPS)
    assert any("Capture target = the mic, recorder, or interface input" in step for step in gui_views.ONLINE_STEPS)
    assert any("headmatch list-targets" in step for step in gui_views.ONLINE_STEPS)


def test_build_doctor_report_reuses_measure_module_formatting(tmp_path, monkeypatch):
    seen = {}

    monkeypatch.setattr("headmatch.gui.collect_doctor_checks", lambda config_path, config: seen.update({"path": config_path, "config": config}) or ["check"])
    monkeypatch.setattr("headmatch.gui.format_doctor_report", lambda checks, *, config_path: f"report for {config_path.name}: {checks[0]}")

    report = build_doctor_report(tmp_path / "config.json", FrontendConfig(pipewire_output_target="usb-dac"))

    assert report == "report for config.json: check"
    assert seen["path"] == tmp_path / "config.json"
    assert seen["config"].pipewire_output_target == "usb-dac"


def test_gui_copy_mentions_setup_and_launch_helpers():
    from headmatch import gui_views

    source = Path(gui_views.__file__).read_text()
    assert "headmatch doctor" in source
    assert "headmatch list-targets" in source
    assert "headmatch-gui" in source
    assert "docs/examples/headmatch.desktop" in source
    assert "~/.local/share/applications/" in source



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
  "confidence": {
    "score": 82,
    "label": "medium",
    "headline": "This run looks usable, but review it before trusting it fully.",
    "interpretation": "Nothing looks catastrophically wrong, but one or more stability signals are only fair.",
    "warnings": ["Residual error is still noticeable."],
    "reasons": [],
    "metrics": {}
  },
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
    assert selection.items[0].summary.out_dir == str(run_dir)
    assert selection.selected_entry is not None
    assert selection.selected_entry.summary.confidence.score == 82
    assert selection.comparison is None



def test_create_app_builds_shell_on_fake_root(tmp_path, fake_tk, monkeypatch):
    created_buttons = []
    original_button = DummyTtk.Button

    class TrackingButton(DummyWidget):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            created_buttons.append(self)

    monkeypatch.setattr(DummyTtk, 'Button', TrackingButton)

    root = DummyRoot()
    app = fake_tk.create_app(
        root=root,
        config_loader=lambda _path=None: (FrontendConfig(default_output_dir=str(tmp_path / 'out' / 'session_01')), tmp_path / 'config.json', False),
    )

    monkeypatch.setattr(DummyTtk, 'Button', original_button)

    nav_labels = [button.kwargs.get('text') for button in created_buttons[:len(NAV_ITEMS)]]

    assert root.title_value == 'HeadMatch 0.2.0'
    assert root.minsize_value == (880, 560)
    assert app.history_root_var.get() == str(tmp_path / 'out')
    assert app.offline_fit_output_var.get().endswith('fit')
    assert nav_labels == ['Measure', 'Setup Check', 'Launch Help', 'Prepare Offline', 'Results']
    assert all('\n' not in label for label in nav_labels)



def test_create_app_includes_launch_help_view(tmp_path, fake_tk):
    root = DummyRoot()
    app = fake_tk.create_app(
        root=root,
        config_loader=lambda _path=None: (FrontendConfig(default_output_dir=str(tmp_path / "out" / "session_01")), tmp_path / "config.json", False),
    )

    app.show_view('launch-help')

    assert app.current_view.get() == 'launch-help'


def test_create_app_includes_setup_check_view_and_refreshes_doctor_report(tmp_path, fake_tk):
    calls = {}
    root = DummyRoot()
    app = fake_tk.create_app(
        root=root,
        config_loader=lambda _path=None: (FrontendConfig(default_output_dir=str(tmp_path / "out" / "session_01")), tmp_path / "config.json", False),
        doctor_report_runner=lambda config_path, config: calls.update({"config_path": config_path, "config": config}) or f"HeadMatch doctor\nConfig path: {config_path}",
    )

    app.show_view('setup-check')

    assert app.doctor_report_var.get().startswith('HeadMatch doctor')
    assert calls['config_path'] == tmp_path / 'config.json'
    assert calls['config'].default_output_dir == str(tmp_path / 'out' / 'session_01')
    assert calls['config'].start_iterations == 1
    assert calls['config'].max_filters == 8


def test_create_app_loads_pipewire_target_dropdowns_with_saved_first(tmp_path, fake_tk, monkeypatch):
    monkeypatch.setattr(
        fake_tk,
        'collect_pipewire_target_selection',
        lambda _config: PipeWireTargetSelection(
            playback_targets=(SimpleNamespace(node_name='alsa_output.usb-dac'),),
            capture_targets=(SimpleNamespace(node_name='alsa_input.usb-mic'),),
            selected_playback='alsa_output.usb-dac',
            selected_capture='alsa_input.usb-mic',
        ),
    )

    root = DummyRoot()
    app = fake_tk.create_app(
        root=root,
        config_loader=lambda _path=None: (
            FrontendConfig(
                default_output_dir=str(tmp_path / 'out' / 'session_01'),
                pipewire_output_target='usb-dac',
                pipewire_input_target='usb-mic',
            ),
            tmp_path / 'config.json',
            False,
        ),
    )

    assert app.output_target_var.get() == 'alsa_output.usb-dac'
    assert app.input_target_var.get() == 'alsa_input.usb-mic'
    assert app.output_target_options == ('alsa_output.usb-dac',)
    assert app.input_target_options == ('alsa_input.usb-mic',)


def test_create_app_keeps_manual_target_fields_usable_when_no_devices_are_detected(tmp_path, fake_tk, monkeypatch):
    created_comboboxes = []
    original_combobox = DummyTtk.Combobox

    class TrackingCombobox(DummyWidget):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            created_comboboxes.append(self)

    monkeypatch.setattr(DummyTtk, 'Combobox', TrackingCombobox)
    monkeypatch.setattr(
        fake_tk,
        'collect_pipewire_target_selection',
        lambda _config: PipeWireTargetSelection(
            playback_targets=(),
            capture_targets=(),
            selected_playback='',
            selected_capture='',
        ),
    )

    root = DummyRoot()
    app = fake_tk.create_app(
        root=root,
        config_loader=lambda _path=None: (FrontendConfig(default_output_dir=str(tmp_path / 'out' / 'session_01')), tmp_path / 'config.json', False),
    )
    app.show_view('measure-online')

    monkeypatch.setattr(DummyTtk, 'Combobox', original_combobox)

    assert app.output_target_options == ()
    assert app.input_target_options == ()
    assert len(created_comboboxes) >= 2
    assert created_comboboxes[-2].kwargs.get('state') == 'normal'
    assert created_comboboxes[-1].kwargs.get('state') == 'normal'


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



def test_load_gui_state_reads_config_file_from_explicit_path(tmp_path):
    suffix = uuid4().hex
    config_path = tmp_path / f"gui-{suffix}.json"
    original = FrontendConfig(
        default_output_dir=f"out/{suffix}",
        preferred_target_csv=f"targets/{suffix}.csv",
        pipewire_output_target=f"playback-{suffix}",
        pipewire_input_target=f"capture-{suffix}",
        start_iterations=7,
        max_filters=5,
    )
    save_config(original, config_path)

    state = load_gui_state(config_path=config_path)

    assert state.config_path == config_path
    assert state.default_output_dir == f"out/{suffix}"
    assert state.preferred_target_csv == f"targets/{suffix}.csv"
    assert state.pipewire_output_target == f"playback-{suffix}"
    assert state.pipewire_input_target == f"capture-{suffix}"
    assert state.start_iterations == 7
    assert state.max_filters == 5


def test_gui_history_selection_builds_recent_run_comparison(tmp_path):
    first = tmp_path / "session_01"
    first.mkdir()
    (first / "README.txt").write_text("first\n")
    (first / "run_summary.json").write_text(
        """{
  "kind": "fit",
  "out_dir": "%s",
  "sample_rate": 48000,
  "frequency_points": 512,
  "target": "flat",
  "filters": {"left": 4, "right": 4},
  "predicted_error_db": {"left_rms": 1.0, "right_rms": 1.1, "left_max": 3.0, "right_max": 3.1},
  "confidence": {
    "score": 82,
    "label": "medium",
    "headline": "This run looks usable, but review it before trusting it fully.",
    "interpretation": "Nothing looks catastrophically wrong, but one or more stability signals are only fair.",
    "warnings": ["Residual error is still noticeable."],
    "reasons": [],
    "metrics": {}
  },
  "results_guide": "%s"
}
""" % (first, first / "README.txt")
    )
    second = tmp_path / "session_02"
    second.mkdir()
    (second / "README.txt").write_text("second\n")
    (second / "run_summary.json").write_text(
        """{
  "kind": "iteration",
  "out_dir": "%s",
  "sample_rate": 44100,
  "frequency_points": 512,
  "target": "custom",
  "filters": {"left": 5, "right": 6},
  "predicted_error_db": {"left_rms": 0.8, "right_rms": 0.9, "left_max": 2.5, "right_max": 2.6},
  "confidence": {
    "score": 90,
    "label": "high",
    "headline": "This run looks trustworthy.",
    "interpretation": "Looks clean.",
    "warnings": [],
    "reasons": [],
    "metrics": {}
  },
  "results_guide": "%s"
}
""" % (second, second / "README.txt")
    )

    first_summary = first / "run_summary.json"
    second_summary = second / "run_summary.json"
    first_summary.touch()
    second_summary.touch()

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

    assert selection.comparison is not None
    assert selection.comparison.left_entry.summary.out_dir == str(second)
    assert selection.comparison.right_entry.summary.out_dir == str(first)
    fields = {field.label: (field.left, field.right) for field in selection.comparison.fields}
    assert fields["Target"] == ("custom", "flat")
    assert fields["Filters (L/R)"] == ("5/6", "4/4")
