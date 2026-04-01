from __future__ import annotations

import pytest

from headmatch import cli


class DummySweepSpec:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


@pytest.fixture(autouse=True)
def patch_sweep_spec(monkeypatch):
    monkeypatch.setattr("headmatch.signals.SweepSpec", DummySweepSpec)


def test_main_without_subcommand_shows_beginner_guide(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main([])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "headmatch beginner path" in out
    assert "headmatch start --out-dir out/session_01" in out


def test_start_dispatches_guided_online_workflow(monkeypatch, capsys, tmp_path):
    calls = {}

    def fake_iterative_measure_and_fit(**kwargs):
        calls.update(kwargs)

    monkeypatch.setattr("headmatch.pipeline.iterative_measure_and_fit", fake_iterative_measure_and_fit)

    cli.main(["start", "--out-dir", str(tmp_path)])

    assert calls["output_dir"] == str(tmp_path)
    assert calls["iterations"] == 1
    assert calls["max_filters"] == 8
    out = capsys.readouterr().out
    assert "Starting guided measurement workflow" in out
    assert "run_summary.json" in out


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
