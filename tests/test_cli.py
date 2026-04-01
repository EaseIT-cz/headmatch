from __future__ import annotations

import pytest

from headmatch import cli
from headmatch.contracts import FrontendConfig


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
    assert "0.2.0" in out
    assert "headmatch start --out-dir out/session_01" in out


def test_version_flag_reports_canonical_version(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    out = capsys.readouterr().out.strip()
    assert out == "headmatch 0.2.0"


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


def test_tui_subcommand_launches_wizard(monkeypatch, capsys):
    calls = {}

    def fake_run_tui(*, stdin, stdout, config_loader):
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

    def fake_run_tui(*, stdin, stdout, config_loader):
        _ = (stdin, stdout, config_loader)
        return type("Result", (), {"workflow": "history", "out_dir": str(tmp_path), "details": str(guide)})()

    monkeypatch.setattr("headmatch.tui.run_tui", fake_run_tui)

    cli.main(["tui"])

    out = capsys.readouterr().out
    assert "History browser finished" in out
    assert str(guide) in out
