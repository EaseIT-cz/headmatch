from __future__ import annotations

from pathlib import Path
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


def test_parse_seconds_accepts_suffix_and_rejects_invalid():
    assert cli.parse_seconds("1.5s") == 1.5
    assert cli.parse_seconds("2") == 2.0
    with pytest.raises(Exception):
        cli.parse_seconds("0")
    with pytest.raises(Exception):
        cli.parse_seconds("abc")


def test_positive_int_rejects_non_positive_and_non_integer():
    assert cli.positive_int("3") == 3
    with pytest.raises(Exception):
        cli.positive_int("0")
    with pytest.raises(Exception):
        cli.positive_int("x")


def test_filter_budget_and_spec_from_args(monkeypatch):
    parser = cli.build_parser(FrontendConfig())
    args = parser.parse_args(["fit", "--recording", "r.wav", "--out-dir", "out", "--filter-family", "graphic_eq", "--graphic-eq-profile", "geq_31_band", "--fill-policy", "exact_n", "--max-filters", "7"])
    budget = cli.filter_budget_from_args(args)
    spec = cli.spec_from_args(args)
    assert budget.family == "graphic_eq"
    assert budget.profile == "geq_31_band"
    assert budget.fill_policy == "exact_n"
    assert budget.max_filters == 7
    assert spec.sample_rate == 48000


def test_run_summary_path_handles_average_and_independent():
    args = type("Args", (), {"out_dir": "/tmp/out", "iteration_mode": "average", "iterations": 3})()
    assert cli._run_summary_path("start", args) == Path("/tmp/out/run_summary.json")
    args = type("Args", (), {"out_dir": "/tmp/out", "iteration_mode": "independent", "iterations": 3})()
    assert cli._run_summary_path("iterate", args) == Path("/tmp/out/iter_03/run_summary.json")
    args = type("Args", (), {"out_dir": None})()
    assert cli._run_summary_path("fit", args) is None


def test_verdict_and_clipping_lines_cover_branches(monkeypatch):
    conf = type("C", (), {"label": "high"})()
    assert "trustworthy" in cli._verdict_line(conf)
    conf.label = "medium"
    assert "Moderate confidence" in cli._verdict_line(conf)
    conf.label = "low"
    assert "Low confidence" in cli._verdict_line(conf)
    assert "No clipping assessment" in cli._clipping_verdict_line(None)
    assert "No EQ clipping" in cli._clipping_verdict_line({"will_clip": False})
    assert "preamp reduction" in cli._clipping_verdict_line({"will_clip": True})


def test_print_clipping_summary_detailed(capsys):
    summary = type("S", (), {"eq_clipping_assessment": {"will_clip": True, "preamp_db": -6.0, "left_peak_boost_db": 7.0, "right_peak_boost_db": 5.0, "headroom_loss_db": 13.0, "left_preamp_db": -6.0, "right_preamp_db": -5.0, "quality_concern": "watch gain"}})()
    cli.print_clipping_summary(summary, detailed=True)
    out = capsys.readouterr().out
    assert "EQ clipping detected" in out
    assert "Preamp recommendation: -6.0 dB" in out
    assert "Detailed clipping breakdown" in out
    assert "watch gain" in out


def test_print_run_confidence_ignores_bad_summary(tmp_path, capsys):
    out_dir = tmp_path / "fit"
    out_dir.mkdir()
    (out_dir / "run_summary.json").write_text("not json", encoding="utf-8")
    cli.print_run_confidence("fit", type("Args", (), {"out_dir": str(out_dir)})())
    assert capsys.readouterr().out == ""


def test_search_headphone_and_fetch_curve_commands(monkeypatch, capsys, tmp_path):
    from headmatch.headphone_db import HeadphoneEntry
    monkeypatch.setattr("headmatch.headphone_db.search_headphone", lambda q: [HeadphoneEntry(name="HD 650", source="oratory1990", form_factor="over-ear", csv_path="results/oratory1990/over-ear/HD 650/HD 650.csv")])
    cli.main(["search-headphone", "HD650"])
    out = capsys.readouterr().out
    assert "Found 1 match" in out
    assert "fetch-curve" in out

    monkeypatch.setattr("headmatch.headphone_db.fetch_curve_from_url", lambda url, out: Path(out))
    cli.main(["fetch-curve", "--url", "https://example.com/a.csv", "--out", str(tmp_path / "a.csv")])
    out = capsys.readouterr().out
    assert "Saved to" in out


def test_import_apo_and_refine_apo_commands(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr("headmatch.apo_import.load_apo_preset", lambda _p: ([1, 2], [3]))
    monkeypatch.setattr("headmatch.exporters.export_equalizer_apo_parametric_txt", lambda *a, **k: None)
    monkeypatch.setattr("headmatch.exporters.export_camilladsp_filters_yaml", lambda *a, **k: None)
    monkeypatch.setattr("headmatch.exporters.export_camilladsp_filter_snippet_yaml", lambda *a, **k: None)
    cli.main(["import-apo", "--preset", "preset.txt", "--out-dir", str(tmp_path / "imported")])
    out = capsys.readouterr().out
    assert "Imported 2 left + 1 right filters" in out

    monkeypatch.setattr("headmatch.apo_refine.refine_apo_preset", lambda **_k: {"original_error": {"left_rms": 4.0, "right_rms": 5.0}, "predicted_left_rms_error_db": 1.5, "predicted_right_rms_error_db": 2.5})
    cli.main(["refine-apo", "--preset", "preset.txt", "--recording", "recording.wav", "--out-dir", str(tmp_path / "refined")])
    out = capsys.readouterr().out
    assert "Refined preset from preset.txt" in out
    assert "After:  L 1.50 dB RMS, R 2.50 dB RMS" in out


def test_clone_target_and_offline_commands(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr("headmatch.pipeline.build_clone_curve", lambda s, t, o: Path(o))
    cli.main(["clone-target", "--source-csv", "a.csv", "--target-csv", "b.csv", "--out", str(tmp_path / "clone.csv")])
    out = capsys.readouterr().out
    assert "Clone target written" in out

    monkeypatch.setattr("headmatch.measure.prepare_offline_measurement", lambda *a, **k: None)
    cli.main(["prepare-offline", "--out-dir", str(tmp_path / "offline")])
    out = capsys.readouterr().out
    assert "Offline package saved" in out

    monkeypatch.setattr("headmatch.analysis.analyze_measurement", lambda *a, **k: None)
    cli.main(["analyze", "--recording", "r.wav", "--out-dir", str(tmp_path / "analysis")])
    out = capsys.readouterr().out
    assert "Analysis written" in out
