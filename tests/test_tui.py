from __future__ import annotations

from io import StringIO
from pathlib import Path
from uuid import uuid4

from headmatch.contracts import FrontendConfig
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
    assert "headmatch fit-offline --recording" in out


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
    suffix = uuid4().hex
    config_path = tmp_path / f"tui-{suffix}.json"
    sample_rate = 43100 + (int(suffix[:2], 16) % 2000)
    duration_s = 5.0 + ((int(suffix[2:4], 16) % 20) / 10)
    f_start_hz = 15.0 + (int(suffix[4:6], 16) % 30)
    f_end_hz = 18000.0 + (int(suffix[6:8], 16) % 3000)
    pre_silence_s = 0.1 + ((int(suffix[8:10], 16) % 5) / 10)
    post_silence_s = 0.6 + ((int(suffix[10:12], 16) % 7) / 10)
    amplitude = 0.1 + ((int(suffix[12:14], 16) % 5) / 100)
    max_filters = 6 + (int(suffix[14:16], 16) % 6)
    start_iterations = 2 + (int(suffix[16:18], 16) % 4)
    iterate_iterations = 3 + (int(suffix[18:20], 16) % 4)
    save_config(
        FrontendConfig(
            default_output_dir=f"out/{suffix}",
            pipewire_output_target=f"playback-{suffix}",
            pipewire_input_target=f"capture-{suffix}",
            preferred_target_csv=f"targets/{suffix}.csv",
            sample_rate=sample_rate,
            duration_s=duration_s,
            f_start_hz=f_start_hz,
            f_end_hz=f_end_hz,
            pre_silence_s=pre_silence_s,
            post_silence_s=post_silence_s,
            amplitude=amplitude,
            max_filters=max_filters,
            start_iterations=start_iterations,
            iterate_iterations=iterate_iterations,
        ),
        config_path,
    )

    calls = {}

    def fake_iterative_measure_and_fit(**kwargs):
        calls.update(kwargs)
        return []

    monkeypatch.setattr("headmatch.tui.iterative_measure_and_fit", fake_iterative_measure_and_fit)

    stdin = StringIO("1\n\n\n\n\n\n\n")
    stdout = StringIO()

    result = tui.run_tui(stdin=stdin, stdout=stdout, config_path=config_path)

    assert result.workflow == "start"
    assert calls["output_dir"] == f"out/{suffix}"
    assert calls["output_target"] == f"playback-{suffix}"
    assert calls["input_target"] == f"capture-{suffix}"
    assert calls["target_path"] == f"targets/{suffix}.csv"
    assert calls["sweep_spec"].sample_rate == sample_rate
    assert calls["sweep_spec"].duration_s == duration_s
    assert calls["sweep_spec"].f_start == f_start_hz
    assert calls["sweep_spec"].f_end == f_end_hz
    assert calls["sweep_spec"].pre_silence_s == pre_silence_s
    assert calls["sweep_spec"].post_silence_s == post_silence_s
    assert calls["sweep_spec"].amplitude == amplitude
    assert calls["max_filters"] == max_filters
    assert calls["iterations"] == start_iterations
    assert f"Config path: {config_path}" in stdout.getvalue()

