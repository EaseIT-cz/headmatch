from __future__ import annotations

import pytest

from headmatch import __version__, cli
from headmatch.contracts import FrontendConfig


class DummySweepSpec:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


@pytest.fixture(autouse=True)
def patch_sweep_spec(monkeypatch, tmp_path):
    monkeypatch.setattr("headmatch.signals.SweepSpec", DummySweepSpec)
    monkeypatch.setattr(
        "headmatch.cli.load_or_create_config",
        lambda _path=None: (FrontendConfig(), tmp_path / "config.json", False),
    )
    monkeypatch.setattr("headmatch.cli.save_config", lambda *_args, **_kwargs: None)


def test_main_without_subcommand_shows_beginner_guide(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main([])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "headmatch beginner path" in out
    assert __version__ in out
    assert "headmatch start --out-dir session_01" in out


def test_version_flag_reports_canonical_version(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    out = capsys.readouterr().out.strip()
    assert out == f"headmatch {__version__}"


def test_start_dispatches_guided_online_workflow(monkeypatch, capsys, tmp_path):
    calls = {}

    monkeypatch.setattr(
        "headmatch.cli.load_or_create_config",
        lambda _path=None: (FrontendConfig(), tmp_path / "config.json", False),
    )

    def fake_iterative_measure_and_fit(**kwargs):
        calls.update(kwargs)

    monkeypatch.setattr("headmatch.pipeline.iterative_measure_and_fit", fake_iterative_measure_and_fit)
    monkeypatch.setattr("headmatch.cli.save_config", lambda *_args, **_kwargs: None)

    cli.main(["start", "--out-dir", str(tmp_path)])

    assert calls["output_dir"] == str(tmp_path)
    assert calls["iterations"] == 1
    assert calls["max_filters"] == 8
    assert calls["filter_budget"].fill_policy == "up_to_n"
    out = capsys.readouterr().out
    assert "Starting guided measurement workflow" in out
    assert "run_summary.json" in out




def test_fit_command_accepts_exact_fill_policy(monkeypatch, tmp_path):
    calls = {}

    def fake_process_single_measurement(*args, **kwargs):
        calls['kwargs'] = kwargs

    monkeypatch.setattr('headmatch.pipeline.process_single_measurement', fake_process_single_measurement)
    monkeypatch.setattr('headmatch.cli.save_config', lambda *_args, **_kwargs: None)

    cli.main([
        'fit',
        '--recording', str(tmp_path / 'recording.wav'),
        '--out-dir', str(tmp_path / 'fit'),
        '--fill-policy', 'exact_n',
        '--max-filters', '5',
    ])

    assert calls['kwargs']['filter_budget'].fill_policy == 'exact_n'
    assert calls['kwargs']['filter_budget'].max_filters == 5

def test_measure_still_dispatches_existing_command(monkeypatch, capsys, tmp_path):
    calls = {}

    def fake_run_pipewire_measurement(spec, paths, device_config):
        calls["spec"] = spec
        calls["paths"] = paths
        calls["device_config"] = device_config

    monkeypatch.setattr("headmatch.measure.run_pipewire_measurement", fake_run_pipewire_measurement)

    cli.main(["measure", "--out-dir", str(tmp_path), "--output-target", "hp", "--input-target", "mic"])

    assert calls["paths"].sweep_wav == tmp_path / "sweep.wav"
    assert calls["paths"].recording_wav == tmp_path / "recording.wav"
    assert calls["device_config"].output_target == "hp"
    assert calls["device_config"].input_target == "mic"
    out = capsys.readouterr().out
    assert "Measurement saved" in out
    assert "headmatch fit --recording" in out


def test_tui_subcommand_launches_wizard(monkeypatch, capsys):
    calls = {}

    def fake_run_tui(*, stdin, stdout, config_loader, config_path=None):
        calls["stdin"] = stdin
        calls["stdout"] = stdout
        calls["config"] = config_loader()

    monkeypatch.setattr("headmatch.tui.run_tui", fake_run_tui)

    cli.main(["tui"])

    assert calls["stdin"] is not None
    assert calls["stdout"] is not None
    assert calls["config"] is not None
    out = capsys.readouterr().out
    assert "Wizard finished" in out


def test_measure_uses_saved_pipewire_targets_when_cli_omits_them(monkeypatch, tmp_path):
    calls = {}

    monkeypatch.setattr(
        "headmatch.cli.load_or_create_config",
        lambda _path=None: (
            FrontendConfig(pipewire_output_target="saved-out", pipewire_input_target="saved-in"),
            tmp_path / "config.json",
            False,
        ),
    )

    def fake_run_pipewire_measurement(spec, paths, device_config):
        calls["device_config"] = device_config

    monkeypatch.setattr("headmatch.measure.run_pipewire_measurement", fake_run_pipewire_measurement)
    monkeypatch.setattr("headmatch.cli.save_config", lambda *_args, **_kwargs: None)

    cli.main(["measure", "--out-dir", str(tmp_path)])

    assert calls["device_config"].output_target == "saved-out"
    assert calls["device_config"].input_target == "saved-in"


def test_cli_explicit_target_overrides_saved_config(monkeypatch, tmp_path):
    calls = {}

    monkeypatch.setattr(
        "headmatch.cli.load_or_create_config",
        lambda _path=None: (
            FrontendConfig(pipewire_output_target="saved-out", pipewire_input_target="saved-in"),
            tmp_path / "config.json",
            False,
        ),
    )

    def fake_run_pipewire_measurement(spec, paths, device_config):
        calls["device_config"] = device_config

    monkeypatch.setattr("headmatch.measure.run_pipewire_measurement", fake_run_pipewire_measurement)
    monkeypatch.setattr("headmatch.cli.save_config", lambda *_args, **_kwargs: None)

    cli.main(["measure", "--out-dir", str(tmp_path), "--output-target", "cli-out"])

    assert calls["device_config"].output_target == "cli-out"
    assert calls["device_config"].input_target == "saved-in"


def test_main_without_subcommand_creates_default_config_notice(monkeypatch, capsys, tmp_path):
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(
        "headmatch.cli.load_or_create_config",
        lambda _path=None: (FrontendConfig(), config_path, True),
    )

    with pytest.raises(SystemExit) as exc:
        cli.main([])

    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert f"Config path: {config_path}" in out
    assert "Created a default config file with safe starter values." in out


def test_tui_history_result_updates_cli_message(monkeypatch, capsys, tmp_path):
    guide = tmp_path / "README.txt"
    guide.write_text("guide\n")

    def fake_run_tui(*, stdin, stdout, config_loader, config_path=None):
        _ = (stdin, stdout, config_loader)
        return type("Result", (), {"workflow": "history", "out_dir": str(tmp_path), "details": str(guide)})()

    monkeypatch.setattr("headmatch.tui.run_tui", fake_run_tui)

    cli.main(["tui"])

    out = capsys.readouterr().out
    assert "History browser finished" in out
    assert str(guide) in out


def test_main_without_subcommand_mentions_doctor_and_list_targets(capsys):
    with pytest.raises(SystemExit):
        cli.main([])
    out = capsys.readouterr().out
    assert "headmatch doctor" in out
    assert "headmatch list-targets" in out


def test_doctor_prints_readiness_report(monkeypatch, capsys, tmp_path):
    from headmatch.measure import DoctorCheck

    config_path = tmp_path / "config.json"
    monkeypatch.setattr(
        "headmatch.cli.load_or_create_config",
        lambda _path=None: (FrontendConfig(pipewire_output_target="hp", pipewire_input_target="mic"), config_path, False),
    )
    monkeypatch.setattr(
        "headmatch.measure.collect_doctor_checks",
        lambda path, config: [
            DoctorCheck(name="config file", ok=True, detail=f"Using {path}"),
            DoctorCheck(name="audio discovery", ok=False, detail="Found 0 playback and 1 capture target(s).", action="Check your output device."),
        ],
    )

    cli.main(["doctor"])

    out = capsys.readouterr().out
    assert "HeadMatch doctor" in out
    assert f"Config path: {config_path}" in out
    assert "Readiness: 1/2 checks look good." in out
    assert "[OK] config file" in out
    assert "[WARN] audio discovery: Found 0 playback and 1 capture target(s)." in out
    assert "- audio discovery: Check your output device." in out


def test_list_targets_prints_pipewire_guidance(monkeypatch, capsys):
    from headmatch.measure import PipeWireTarget

    monkeypatch.setattr(
        "headmatch.measure.list_pipewire_targets",
        lambda: [
            PipeWireTarget(
                kind="playback",
                device_id="alsa_output.usb-dac",
                label="USB DAC",
                description="USB DAC",
                raw_info={"node_name": "alsa_output.usb-dac", "nick": "", "media_class": "Audio/Sink"},
            ),
            PipeWireTarget(
                kind="capture",
                device_id="alsa_input.usb-mic",
                label="USB Mic",
                description="USB Mic",
                raw_info={"node_name": "alsa_input.usb-mic", "nick": "", "media_class": "Audio/Source"},
            ),
        ],
    )

    cli.main(["list-targets"])

    out = capsys.readouterr().out
    assert "Playback targets (--output-target)" in out
    assert "USB DAC -> alsa_output.usb-dac" in out
    assert "Capture targets (--input-target)" in out
    assert "USB Mic -> alsa_input.usb-mic" in out


def test_start_next_steps_mentions_list_targets(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr("headmatch.pipeline.iterative_measure_and_fit", lambda **_kwargs: None)

    cli.main(["start", "--out-dir", str(tmp_path)])

    out = capsys.readouterr().out
    assert "headmatch list-targets" in out


def test_fit_next_steps_prints_confidence_summary(capsys, tmp_path):
    summary_dir = tmp_path / "fit"
    summary_dir.mkdir()
    (summary_dir / "run_summary.json").write_text(
        """{
  "schema_version": 1,
  "kind": "fit",
  "out_dir": "/tmp/demo",
  "sample_rate": 48000,
  "frequency_points": 2048,
  "target": "flat_target",
  "filters": {"left": 4, "right": 4},
  "predicted_error_db": {"left_rms": 1.5, "right_rms": 1.6, "left_max": 3.1, "right_max": 3.0},
  "generated_by": {"name": "headmatch"},
  "confidence": {
    "score": 82,
    "label": "medium",
    "headline": "This run looks usable, but review it before trusting it fully.",
    "interpretation": "Some signals are only fair.",
    "reasons": [],
    "warnings": ["Check the graphs."],
    "metrics": {}
  },
  "plots": {},
  "results_guide": "/tmp/demo/README.txt"
}"""
    )

    cli.print_next_steps("fit", type("Args", (), {"out_dir": str(summary_dir)})())

    out = capsys.readouterr().out
    assert "Confidence: Medium (82/100)" in out
    assert "Some signals are only fair." in out
    assert "Warning: Check the graphs." in out
    assert "Troubleshooting:" in out
    assert "Open the fit graphs before using the preset" in out

def test_fit_next_steps_prints_clipping_summary(capsys, tmp_path):
    summary_dir = tmp_path / "fit"
    summary_dir.mkdir()
    (summary_dir / "run_summary.json").write_text(
        """{
  "schema_version": 1,
  "kind": "fit",
  "out_dir": "/tmp/demo",
  "sample_rate": 48000,
  "frequency_points": 2048,
  "target": "flat_target",
  "filters": {"left": 4, "right": 4},
  "predicted_error_db": {"left_rms": 1.5, "right_rms": 1.6, "left_max": 3.1, "right_max": 3.0},
  "generated_by": {"name": "headmatch"},
  "confidence": {
    "score": 82,
    "label": "medium",
    "headline": "This run looks usable, but review it before trusting it fully.",
    "interpretation": "Some signals are only fair.",
    "reasons": [],
    "warnings": ["Check the graphs."],
    "metrics": {}
  },
  "eq_clipping_assessment": {
    "will_clip": true,
    "left_peak_boost_db": 7.25,
    "right_peak_boost_db": 4.0,
    "left_preamp_db": -7.25,
    "right_preamp_db": -4.0,
    "preamp_db": -7.25,
    "headroom_loss_db": 7.25,
    "quality_concern": "Moderate headroom loss (7.3 dB)."
  },
  "plots": {},
  "results_guide": "/tmp/demo/README.txt"
}"""
    )

    cli.print_next_steps("fit", type("Args", (), {"out_dir": str(summary_dir)})())

    out = capsys.readouterr().out
    assert "Preamp recommendation: -7.2 dB" in out
    assert "Max boost level: 7.2 dB" in out
    assert "moderate headroom loss" in out


def test_fit_next_steps_show_clipping_details(capsys, tmp_path):
    summary_dir = tmp_path / "fit"
    summary_dir.mkdir()
    (summary_dir / "run_summary.json").write_text(
        """{
  "schema_version": 1,
  "kind": "fit",
  "out_dir": "/tmp/demo",
  "sample_rate": 48000,
  "frequency_points": 2048,
  "target": "flat_target",
  "filters": {"left": 4, "right": 4},
  "predicted_error_db": {"left_rms": 1.5, "right_rms": 1.6, "left_max": 3.1, "right_max": 3.0},
  "generated_by": {"name": "headmatch"},
  "confidence": {"score": 82, "label": "medium", "headline": "x", "interpretation": "y", "reasons": [], "warnings": [], "metrics": {}},
  "eq_clipping_assessment": {"will_clip": true, "left_peak_boost_db": 7.25, "right_peak_boost_db": 4.0, "left_preamp_db": -7.25, "right_preamp_db": -4.0, "preamp_db": -7.25, "headroom_loss_db": 7.25, "quality_concern": "Moderate headroom loss (7.3 dB)."},
  "plots": {},
  "results_guide": "/tmp/demo/README.txt"
}"""
    )

    cli.print_next_steps("fit", type("Args", (), {"out_dir": str(summary_dir), "show_clipping": True})())

    out = capsys.readouterr().out
    assert "Detailed clipping breakdown:" in out
    assert "Left peak boost" in out


def test_start_next_steps_reads_last_iteration_confidence(capsys, tmp_path):
    iter_dir = tmp_path / "iter_02"
    iter_dir.mkdir(parents=True)
    (iter_dir / "run_summary.json").write_text(
        """{
  "schema_version": 1,
  "kind": "iteration",
  "out_dir": "/tmp/demo/iter_02",
  "sample_rate": 48000,
  "frequency_points": 2048,
  "target": "flat_target",
  "filters": {"left": 4, "right": 4},
  "predicted_error_db": {"left_rms": 1.5, "right_rms": 1.6, "left_max": 3.1, "right_max": 3.0},
  "generated_by": {"name": "headmatch"},
  "confidence": {
    "score": 91,
    "label": "high",
    "headline": "This run looks trustworthy.",
    "interpretation": "The main stability signals look clean.",
    "reasons": [],
    "warnings": [],
    "metrics": {}
  },
  "plots": {},
  "results_guide": "/tmp/demo/iter_02/README.txt"
}"""
    )

    cli.print_next_steps("start", type("Args", (), {"out_dir": str(tmp_path), "iterations": 2})())

    out = capsys.readouterr().out
    assert "Confidence: High (91/100)" in out
    assert "The main stability signals look clean." in out


def test_fit_json_output_includes_clipping_assessment(monkeypatch, capsys, tmp_path):
    summary = {
        "schema_version": 1,
        "kind": "fit",
        "out_dir": str(tmp_path / "fit"),
        "sample_rate": 48000,
        "frequency_points": 2048,
        "target": "flat_target",
        "filters": {"left": 4, "right": 4},
        "predicted_error_db": {"left_rms": 1.5, "right_rms": 1.6, "left_max": 3.1, "right_max": 3.0},
        "generated_by": {"name": "headmatch"},
        "confidence": {"score": 82, "label": "medium", "headline": "x", "interpretation": "y", "reasons": [], "warnings": [], "metrics": {}},
        "eq_clipping_assessment": {"will_clip": True, "preamp_db": -7.25},
        "plots": {},
        "results_guide": "/tmp/demo/README.txt",
    }

    def fake_process_single_measurement(*_args, **_kwargs):
        out_dir = tmp_path / "fit"
        out_dir.mkdir()
        (out_dir / "run_summary.json").write_text(__import__("json").dumps(summary))

    monkeypatch.setattr("headmatch.pipeline.process_single_measurement", fake_process_single_measurement)
    monkeypatch.setattr("headmatch.cli.save_config", lambda *_args, **_kwargs: None)

    cli.main(["fit", "--recording", str(tmp_path / "recording.wav"), "--out-dir", str(tmp_path / "fit"), "--json"])

    out = capsys.readouterr().out
    assert '"eq_clipping_assessment"' in out
    assert '"preamp_db": -7.25' in out
