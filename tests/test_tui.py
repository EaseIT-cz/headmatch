from __future__ import annotations

from io import StringIO

from headmatch.contracts import FrontendConfig
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

    result = tui.run_tui(stdin=stdin, stdout=stdout, config_loader=lambda: config)

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


def test_run_tui_offline_writes_measurement_plan(monkeypatch, tmp_path):
    calls = {}

    def fake_prepare_offline_measurement(spec, plan):
        calls["spec"] = spec
        calls["plan"] = plan
        return {"ok": True}

    monkeypatch.setattr("headmatch.tui.prepare_offline_measurement", fake_prepare_offline_measurement)

    stdin = StringIO(f"2\n{tmp_path}\n\n\n\n5\n1\nbring recorder\n")
    stdout = StringIO()

    result = tui.run_tui(stdin=stdin, stdout=stdout)

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

    result = tui.run_tui(stdin=stdin, stdout=stdout, config_loader=lambda: config)

    assert result.workflow == "history"
    assert result.out_dir == str(run_dir)
    out = stdout.getvalue()
    assert "Recent runs" in out
    assert "headmatch fit results" in out
    assert "predicted error dB" in out
