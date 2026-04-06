from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import sys

import pytest

from headmatch import __version__
from headmatch.contracts import FrontendConfig
from tests.config_fixtures import varied_config
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


class DummyFileDialog:
    def askdirectory(self, **_kwargs):
        return ""

    def askopenfilename(self, **_kwargs):
        return ""


DummyTtk.Style = DummyStyle


@pytest.fixture
def fake_tk(monkeypatch):
    import headmatch.gui as gui

    monkeypatch.setitem(sys.modules, 'tkinter', SimpleNamespace(StringVar=DummyVar, ttk=DummyTtk, Canvas=DummyWidget))
    monkeypatch.setitem(sys.modules, 'tkinter.ttk', DummyTtk)
    monkeypatch.setattr(gui, 'filedialog', DummyFileDialog())
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

    assert state.version_display == __version__
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

    assert "Documents/HeadMatch/session_01" in state.default_output_dir
    assert state.preferred_target_csv == ""
    assert state.pipewire_output_target == ""
    assert state.pipewire_input_target == ""
    assert state.config_created is True



def test_navigation_items_cover_shell_sections():
    assert [item.key for item in NAV_ITEMS] == [
        "measure-online",
        "setup-check",
        "prepare-offline",
        "target-editor",
        "import-apo",
        "fetch-curve",
        "history",
    ]
    assert [item.label for item in NAV_ITEMS] == [
        "Measure", "Setup Check", "Prepare Offline",
        "Target Editor", "Import APO", "Fetch Curve", "Results",
    ]



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


def test_gui_copy_mentions_setup_helpers():
    from headmatch import gui_views

    source = Path(gui_views.__file__).read_text()
    assert "headmatch doctor" in source
    assert "headmatch list-targets" in source



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

    assert root.title_value == f'HeadMatch {__version__}'
    assert root.minsize_value == (880, 560)
    assert app.history_root_var.get() == str(tmp_path / 'out')
    assert app.offline_fit_output_var.get().endswith('fit')
    assert nav_labels == ['Measure', 'Setup Check', 'Prepare Offline', 'Target Editor', 'Import APO', 'Fetch Curve', 'Results']
    assert all('\n' not in label for label in nav_labels)



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
            playback_targets=(SimpleNamespace(device_id='alsa_output.usb-dac', label='USB DAC'),),
            capture_targets=(SimpleNamespace(device_id='alsa_input.usb-mic', label='USB Mic'),),
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

    assert app.output_target_var.get() == 'alsa_output.usb-dac — USB DAC'
    assert app.input_target_var.get() == 'alsa_input.usb-mic — USB Mic'
    assert app.output_target_options == ('alsa_output.usb-dac — USB DAC',)
    assert app.input_target_options == ('alsa_input.usb-mic — USB Mic',)


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
    # Device target comboboxes are the first two — check those, not the iteration mode combobox
    device_combos = [c for c in created_comboboxes if c.kwargs.get("state") == "normal"]
    assert len(device_combos) >= 2



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
    suffix, original = varied_config()
    config_path = tmp_path / f"gui-{suffix}.json"
    save_config(original, config_path)

    state = load_gui_state(config_path=config_path)

    assert state.config_path == config_path
    assert state.default_output_dir == original.default_output_dir
    assert state.preferred_target_csv == original.preferred_target_csv
    assert state.pipewire_output_target == original.pipewire_output_target
    assert state.pipewire_input_target == original.pipewire_input_target
    assert state.sample_rate == original.sample_rate
    assert state.duration_s == original.duration_s
    assert state.f_start_hz == original.f_start_hz
    assert state.f_end_hz == original.f_end_hz
    assert state.pre_silence_s == original.pre_silence_s
    assert state.post_silence_s == original.post_silence_s
    assert state.amplitude == original.amplitude
    assert state.start_iterations == original.start_iterations
    assert state.max_filters == original.max_filters

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


def test_gui_views_include_browse_buttons_for_major_path_fields():
    from headmatch import gui_views

    source = Path(gui_views.__file__).read_text()
    assert source.count('button_text="Browse…"') >= 5


def test_choose_output_dir_updates_entry_but_keeps_manual_editing_available(tmp_path, fake_tk, monkeypatch):
    root = DummyRoot()
    app = fake_tk.create_app(
        root=root,
        config_loader=lambda _path=None: (FrontendConfig(default_output_dir=str(tmp_path / 'out' / 'session_01')), tmp_path / 'config.json', False),
    )

    monkeypatch.setattr(fake_tk.filedialog, 'askdirectory', lambda **kwargs: str(tmp_path / 'chosen-output'))

    app.output_dir_var.set('manual/output')
    app.choose_output_dir()

    assert app.output_dir_var.get() == str(tmp_path / 'chosen-output')
    app.output_dir_var.set('manual/override')
    assert app.output_dir_var.get() == 'manual/override'


def test_choose_target_csv_uses_native_picker_for_csv_fields(tmp_path, fake_tk, monkeypatch):
    root = DummyRoot()
    app = fake_tk.create_app(
        root=root,
        config_loader=lambda _path=None: (FrontendConfig(default_output_dir=str(tmp_path / 'out' / 'session_01')), tmp_path / 'config.json', False),
    )

    seen = {}

    def fake_open(**kwargs):
        seen.update(kwargs)
        return str(tmp_path / 'targets' / 'custom.csv')

    monkeypatch.setattr(fake_tk.filedialog, 'askopenfilename', fake_open)

    app.choose_target_csv()

    assert app.target_csv_var.get() == str(tmp_path / 'targets' / 'custom.csv')
    assert seen['title'] == 'Choose target CSV'
    assert ('CSV files', '*.csv') in seen['filetypes']


def test_choose_offline_recording_and_fit_output_use_native_pickers(tmp_path, fake_tk, monkeypatch):
    root = DummyRoot()
    app = fake_tk.create_app(
        root=root,
        config_loader=lambda _path=None: (FrontendConfig(default_output_dir=str(tmp_path / 'offline')), tmp_path / 'config.json', False),
    )

    open_calls = {}
    dir_calls = {}

    monkeypatch.setattr(fake_tk.filedialog, 'askopenfilename', lambda **kwargs: open_calls.update(kwargs) or str(tmp_path / 'captures' / 'recording.wav'))
    monkeypatch.setattr(fake_tk.filedialog, 'askdirectory', lambda **kwargs: dir_calls.update(kwargs) or str(tmp_path / 'offline-fit'))

    app.choose_offline_recording()
    app.choose_offline_fit_output_dir()

    assert app.offline_recording_var.get() == str(tmp_path / 'captures' / 'recording.wav')
    assert app.offline_fit_output_var.get() == str(tmp_path / 'offline-fit')
    assert open_calls['title'] == 'Choose recorded WAV'
    assert ('WAV files', '*.wav') in open_calls['filetypes']
    assert dir_calls['title'] == 'Choose fit output folder'


def test_picker_cancel_leaves_existing_values_unchanged(tmp_path, fake_tk, monkeypatch):
    root = DummyRoot()
    app = fake_tk.create_app(
        root=root,
        config_loader=lambda _path=None: (FrontendConfig(default_output_dir=str(tmp_path / 'offline')), tmp_path / 'config.json', False),
    )

    app.target_csv_var.set('manual-target.csv')
    app.offline_recording_var.set('manual-recording.wav')
    monkeypatch.setattr(fake_tk.filedialog, 'askopenfilename', lambda **kwargs: '')

    app.choose_target_csv()
    app.choose_offline_recording()

    assert app.target_csv_var.get() == 'manual-target.csv'
    assert app.offline_recording_var.get() == 'manual-recording.wav'


# ── TASK-078: Curve preview tests ──

class TestCurvePreview:
    """Verify the curve preview canvas renders without errors."""

    def test_render_curve_preview_flat_editor(self):
        """Flat default target should render without errors."""
        from headmatch.gui_views import _render_curve_preview
        from headmatch.target_editor import TargetEditor

        class FakeCanvas:
            def __init__(self):
                self.items = []
            def delete(self, *args):
                pass
            def create_rectangle(self, *args, **kwargs):
                self.items.append(('rect', args, kwargs))
                return len(self.items)
            def create_line(self, *args, **kwargs):
                self.items.append(('line', args, kwargs))
                return len(self.items)
            def create_text(self, *args, **kwargs):
                self.items.append(('text', args, kwargs))
                return len(self.items)
            def create_oval(self, *args, **kwargs):
                self.items.append(('oval', args, kwargs))
                return len(self.items)

        canvas = FakeCanvas()
        editor = TargetEditor()
        _render_curve_preview(canvas, editor)

        # Should have drawn grid, reference line, curve, and control points
        line_items = [i for i in canvas.items if i[0] == 'line']
        oval_items = [i for i in canvas.items if i[0] == 'oval']
        assert len(line_items) > 5, "Expected grid lines + curve"
        assert len(oval_items) == len(editor.points), "Expected one oval per control point"

    def test_render_curve_preview_with_boost(self):
        """Editor with a 1kHz boost should produce a different curve than flat."""
        from headmatch.gui_views import _render_curve_preview
        from headmatch.target_editor import TargetEditor

        class FakeCanvas:
            def __init__(self):
                self.items = []
            def delete(self, *args):
                pass
            def create_rectangle(self, *args, **kwargs):
                self.items.append(('rect', args, kwargs))
                return len(self.items)
            def create_line(self, *args, **kwargs):
                self.items.append(('line', args, kwargs))
                return len(self.items)
            def create_text(self, *args, **kwargs):
                self.items.append(('text', args, kwargs))
                return len(self.items)
            def create_oval(self, *args, **kwargs):
                self.items.append(('oval', args, kwargs))
                return len(self.items)

        # Flat
        flat_canvas = FakeCanvas()
        flat_editor = TargetEditor()
        _render_curve_preview(flat_canvas, flat_editor)

        # Boosted at 1kHz (move existing 1kHz point to +6 dB)
        boost_canvas = FakeCanvas()
        boost_editor = TargetEditor()
        boost_editor.move_point(2, 1000.0, 6.0)  # index 2 is the 1kHz point
        _render_curve_preview(boost_canvas, boost_editor)

        # The curve line coordinates should differ
        flat_curves = [i for i in flat_canvas.items if i[0] == 'line' and i[2].get('fill') == '#00ccaa']
        boost_curves = [i for i in boost_canvas.items if i[0] == 'line' and i[2].get('fill') == '#00ccaa']
        assert len(flat_curves) >= 1
        assert len(boost_curves) >= 1
        # The actual polyline coords should differ
        assert flat_curves[0][1] != boost_curves[0][1], "Boosted curve should differ from flat"


# ── TASK-086: Plot geometry coordinate round-trip tests ──

class TestPlotGeometry:
    """Verify freq/dB ↔ pixel coordinate conversions are invertible."""

    def test_freq_round_trip(self):
        from headmatch.gui_views import _PlotGeometry
        geom = _PlotGeometry(560, 200)
        for freq in [20.0, 100.0, 1000.0, 10000.0, 20000.0]:
            x = geom.freq_to_x(freq)
            recovered = geom.x_to_freq(x)
            assert abs(recovered - freq) / freq < 0.01, f"freq round-trip failed for {freq}: got {recovered}"

    def test_db_round_trip(self):
        from headmatch.gui_views import _PlotGeometry
        geom = _PlotGeometry(560, 200)
        for db in [-20.0, -10.0, 0.0, 10.0, 20.0]:
            y = geom.db_to_y(db)
            recovered = geom.y_to_db(y)
            assert abs(recovered - db) < 0.1, f"dB round-trip failed for {db}: got {recovered}"

    def test_x_to_freq_clamps(self):
        from headmatch.gui_views import _PlotGeometry
        geom = _PlotGeometry(560, 200)
        # Way outside the plot area should clamp, not crash
        f_left = geom.x_to_freq(-100)
        f_right = geom.x_to_freq(1000)
        assert 20.0 <= f_left <= 20000.0
        assert 20.0 <= f_right <= 20000.0

    def test_y_to_db_clamps(self):
        from headmatch.gui_views import _PlotGeometry
        geom = _PlotGeometry(560, 200)
        db_top = geom.y_to_db(-100)
        db_bot = geom.y_to_db(500)
        assert -20.0 <= db_top <= 20.0
        assert -20.0 <= db_bot <= 20.0


class TestCurvePreviewWithAddedPoints:
    """Verify the curve preview works correctly with dynamically added points."""

    def _make_fake_canvas(self):
        class FakeCanvas:
            def __init__(self):
                self.items = []
            def delete(self, *args):
                self.items.clear()
            def create_rectangle(self, *args, **kwargs):
                self.items.append(('rect', args, kwargs))
                return len(self.items)
            def create_line(self, *args, **kwargs):
                self.items.append(('line', args, kwargs))
                return len(self.items)
            def create_text(self, *args, **kwargs):
                self.items.append(('text', args, kwargs))
                return len(self.items)
            def create_oval(self, *args, **kwargs):
                self.items.append(('oval', args, kwargs))
                return len(self.items)
            def tag_bind(self, *args, **kwargs):
                pass
        return FakeCanvas()

    def test_render_with_added_point(self):
        from headmatch.gui_views import _render_curve_preview
        from headmatch.target_editor import TargetEditor
        editor = TargetEditor()
        editor.add_point(500.0, 5.0)
        assert len(editor.points) == 7
        canvas = self._make_fake_canvas()
        _render_curve_preview(canvas, editor)
        ovals = [i for i in canvas.items if i[0] == 'oval']
        assert len(ovals) == 7, f"Expected 7 control points, got {len(ovals)}"

    def test_render_with_many_points(self):
        from headmatch.gui_views import _render_curve_preview
        from headmatch.target_editor import TargetEditor
        editor = TargetEditor()
        # Add many points
        for freq in [30, 50, 80, 150, 300, 600, 800, 1500, 2500, 3500, 7000, 12000, 15000]:
            editor.add_point(float(freq), 0.0)
        assert len(editor.points) > 15
        canvas = self._make_fake_canvas()
        _render_curve_preview(canvas, editor)
        ovals = [i for i in canvas.items if i[0] == 'oval']
        assert len(ovals) == len(editor.points), \
            f"Expected {len(editor.points)} control points, got {len(ovals)}"

    def test_render_with_minimum_points(self):
        from headmatch.gui_views import _render_curve_preview
        from headmatch.target_editor import TargetEditor, ControlPoint
        editor = TargetEditor(points=[
            ControlPoint(20.0, 0.0),
            ControlPoint(20000.0, 0.0),
        ])
        canvas = self._make_fake_canvas()
        _render_curve_preview(canvas, editor)
        ovals = [i for i in canvas.items if i[0] == 'oval']
        assert len(ovals) == 2
