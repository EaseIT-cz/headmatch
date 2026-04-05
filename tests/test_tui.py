from __future__ import annotations

from io import StringIO
from pathlib import Path
from uuid import uuid4

from headmatch.contracts import FrontendConfig
from tests.config_fixtures import varied_config
from headmatch.settings import save_config
from headmatch import tui


def test_run_tui_online_reuses_pipeline_and_preloads_saved_device_values(monkeypatch):
    calls = {}

    def fake_iterative_measure_and_fit(**kwargs):
        calls.update(kwargs)
        return []

    monkeypatch.setattr("headmatch.tui.iterative_measure_and_fit", fake_iterative_measure_and_fit)

    config = FrontendConfig(
        default_output_dir="saved/session",
        pipewire_output_target="speakers",
        pipewire_input_target="in-ear-mic",
        preferred_target_csv="targets/custom.csv",
        max_filters=6,
        start_iterations=2,
    )
    stdin = StringIO("1\n\n\n\n\n\n\n")
    stdout = StringIO()

    result = tui.run_tui(stdin=stdin, stdout=stdout, config_loader=lambda _path=None: (config, Path("/tmp/config.json"), False))

    assert result.workflow == "start"
    assert calls["output_dir"] == "saved/session"
    assert calls["output_target"] == "speakers"
    assert calls["input_target"] == "in-ear-mic"
    assert calls["target_path"] == "targets/custom.csv"
    assert calls["max_filters"] == 6
    assert calls["iterations"] == 2
    out = stdout.getvalue()
    assert "Saved device targets were found" in out
    assert "Step 2/3: running measure -> analyze -> fit" in out


def test_run_tui_without_saved_targets_mentions_doctor_and_list_targets(monkeypatch):
    monkeypatch.setattr("headmatch.tui.iterative_measure_and_fit", lambda **_kwargs: [])

    stdin = StringIO("1\n\n\n\n\n\n\n")
    stdout = StringIO()

    tui.run_tui(stdin=stdin, stdout=stdout, config_loader=lambda _path=None: (FrontendConfig(), Path("/tmp/config.json"), False))

    out = stdout.getvalue()
    assert "headmatch doctor" in out
    assert "headmatch list-targets" in out


def test_run_tui_offline_writes_measurement_plan(monkeypatch, tmp_path):
    calls = {}

    def fake_prepare_offline_measurement(spec, plan):
        calls["spec"] = spec
        calls["plan"] = plan
        return {"ok": True}

    monkeypatch.setattr("headmatch.tui.prepare_offline_measurement", fake_prepare_offline_measurement)

    stdin = StringIO(f"2\n{tmp_path}\n\n\n\n5\n1\nbring recorder\n")
    stdout = StringIO()

    result = tui.run_tui(stdin=stdin, stdout=stdout, config_loader=lambda _path=None: (FrontendConfig(), Path("/tmp/config.json"), False))

    assert result.workflow == "prepare-offline"
    assert calls["plan"].sweep_wav == tmp_path / "sweep.wav"
    assert calls["plan"].metadata_json == tmp_path / "measurement_plan.json"
    assert calls["plan"].notes == "bring recorder"
    out = stdout.getvalue()
    assert "Step 1/2: writing the offline sweep package" in out
    assert "headmatch fit --recording" in out


def test_run_tui_history_browser_shows_recent_run(tmp_path):
    run_dir = tmp_path / "session_01"
    run_dir.mkdir()
    (run_dir / "README.txt").write_text("headmatch fit results\n")
    (run_dir / "run_summary.json").write_text(
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
""" % (run_dir, run_dir / "README.txt")
    )

    config = FrontendConfig(default_output_dir=str(tmp_path / "saved" / "session"))
    stdin = StringIO(f"3\n{tmp_path}\n1\n")
    stdout = StringIO()

    result = tui.run_tui(stdin=stdin, stdout=stdout, config_loader=lambda _path=None: (config, Path("/tmp/config.json"), False))

    assert result.workflow == "history"
    assert result.out_dir == str(run_dir)
    out = stdout.getvalue()
    assert "Recent runs" in out
    assert "headmatch fit results" in out
    assert "predicted error dB" in out



def test_run_tui_persists_selected_targets(monkeypatch, tmp_path):
    saved = {}

    def fake_save_config(config, path):
        saved["config"] = config
        saved["path"] = path
        return path

    def fake_iterative_measure_and_fit(**kwargs):
        return []

    monkeypatch.setattr("headmatch.tui.save_config", fake_save_config)
    monkeypatch.setattr("headmatch.tui.iterative_measure_and_fit", fake_iterative_measure_and_fit)

    config = FrontendConfig()
    stdin = StringIO("1\nout/session_02\nout-node\nin-node\n\n\n\n")
    stdout = StringIO()

    tui.run_tui(
        stdin=stdin,
        stdout=stdout,
        config_loader=lambda _path=None: (config, tmp_path / "config.json", False),
    )

    assert saved["path"] == tmp_path / "config.json"
    assert saved["config"].pipewire_output_target == "out-node"
    assert saved["config"].pipewire_input_target == "in-node"
    assert saved["config"].default_output_dir == "out/session_02"



def test_run_tui_reads_explicit_config_file_with_randomized_values(monkeypatch, tmp_path):
    suffix, config = varied_config()
    config_path = tmp_path / f"tui-{suffix}.json"
    save_config(config, config_path)

    calls = {}

    def fake_iterative_measure_and_fit(**kwargs):
        calls.update(kwargs)
        return []

    monkeypatch.setattr("headmatch.tui.iterative_measure_and_fit", fake_iterative_measure_and_fit)

    stdin = StringIO("1\n\n\n\n\n\n\n")
    stdout = StringIO()

    result = tui.run_tui(stdin=stdin, stdout=stdout, config_path=config_path)

    assert result.workflow == "start"
    assert calls["output_dir"] == config.default_output_dir
    assert calls["output_target"] == config.pipewire_output_target
    assert calls["input_target"] == config.pipewire_input_target
    assert calls["target_path"] == config.preferred_target_csv
    assert calls["sweep_spec"].sample_rate == config.sample_rate
    assert calls["sweep_spec"].duration_s == config.duration_s
    assert calls["sweep_spec"].f_start == config.f_start_hz
    assert calls["sweep_spec"].f_end == config.f_end_hz
    assert calls["sweep_spec"].pre_silence_s == config.pre_silence_s
    assert calls["sweep_spec"].post_silence_s == config.post_silence_s
    assert calls["sweep_spec"].amplitude == config.amplitude
    assert calls["max_filters"] == config.max_filters
    assert calls["iterations"] == config.start_iterations
    assert f"Config path: {config_path}" in stdout.getvalue()

