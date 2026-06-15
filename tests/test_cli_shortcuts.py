"""End-to-end tests for the `create-shortcut` / `remove-shortcut` CLI commands
and their Linux gate.

These commands are registered in build_parser only on Linux (desktop .desktop
launchers are an XDG concept). The handlers drive headmatch.desktop, which is
tested directly in test_desktop.py; here we cover the CLI wiring and the gate.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from headmatch import cli
from headmatch.contracts import FrontendConfig


@pytest.fixture(autouse=True)
def isolate_cli_config(monkeypatch, tmp_path):
    """Keep cli.main from touching real config state."""
    monkeypatch.setattr(
        "headmatch.cli.load_or_create_config",
        lambda _path=None: (FrontendConfig(), tmp_path / "config.json", False),
    )
    monkeypatch.setattr("headmatch.cli.save_config", lambda *_a, **_k: None)


@pytest.fixture
def fake_apps(tmp_path, monkeypatch):
    """Point the desktop entry dir at a temp dir so nothing writes to ~/."""
    apps = tmp_path / "applications"
    monkeypatch.setattr("headmatch.desktop.DESKTOP_DIR", apps)
    return apps


# ── create-shortcut ──────────────────────────────────────────────────────────


def test_create_shortcut_cli_writes_desktop_file(fake_apps, monkeypatch, capsys):
    monkeypatch.setattr("headmatch.desktop.find_gui_binary", lambda: "/usr/bin/headmatch-gui")

    cli.main(["create-shortcut"])

    desktop_file = fake_apps / "headmatch.desktop"
    assert desktop_file.exists()
    content = desktop_file.read_text()
    assert "Exec=/usr/bin/headmatch-gui" in content
    assert "Name=HeadMatch" in content

    out = capsys.readouterr().out
    assert "Desktop shortcut created" in out
    assert "/usr/bin/headmatch-gui" in out


def test_create_shortcut_cli_reports_missing_gui_binary(fake_apps, monkeypatch, capsys):
    monkeypatch.setattr("headmatch.desktop.find_gui_binary", lambda: None)

    cli.main(["create-shortcut"])

    assert not (fake_apps / "headmatch.desktop").exists()
    out = capsys.readouterr().out
    assert "Could not find headmatch-gui" in out


# ── remove-shortcut ──────────────────────────────────────────────────────────


def test_remove_shortcut_cli_removes_existing(fake_apps, capsys):
    fake_apps.mkdir(parents=True, exist_ok=True)
    target = fake_apps / "headmatch.desktop"
    target.write_text("[Desktop Entry]\n")

    cli.main(["remove-shortcut"])

    assert not target.exists()
    assert "Desktop shortcut removed" in capsys.readouterr().out


def test_remove_shortcut_cli_when_absent(fake_apps, capsys):
    cli.main(["remove-shortcut"])

    assert "No desktop shortcut found" in capsys.readouterr().out


# ── Linux gate ───────────────────────────────────────────────────────────────


def test_shortcut_commands_unregistered_off_linux(monkeypatch):
    """On non-Linux platforms the subcommands are not registered, so argparse
    rejects them with a SystemExit before any handler runs."""
    monkeypatch.setattr(cli, "_desktop_shortcuts_supported", lambda: False)

    for cmd in ("create-shortcut", "remove-shortcut"):
        with pytest.raises(SystemExit):
            cli.main([cmd])


def test_shortcut_commands_registered_on_linux(monkeypatch):
    monkeypatch.setattr(cli, "_desktop_shortcuts_supported", lambda: True)
    parser = cli.build_parser(FrontendConfig())
    # The subparsers action holds the registered command choices.
    choices = parser.parse_args(["remove-shortcut"]).cmd
    assert choices == "remove-shortcut"


def test_desktop_shortcuts_supported_tracks_platform(monkeypatch):
    monkeypatch.setattr("headmatch.cli.sys.platform", "linux")
    assert cli._desktop_shortcuts_supported() is True
    monkeypatch.setattr("headmatch.cli.sys.platform", "darwin")
    assert cli._desktop_shortcuts_supported() is False
    monkeypatch.setattr("headmatch.cli.sys.platform", "win32")
    assert cli._desktop_shortcuts_supported() is False


# ── doctor tip is gated too ──────────────────────────────────────────────────


def _patch_doctor_report(monkeypatch):
    monkeypatch.setattr("headmatch.measure.collect_doctor_checks", lambda path, config: [])
    monkeypatch.setattr(
        "headmatch.measure.format_doctor_report",
        lambda checks, config_path: "HeadMatch doctor report",
    )


def test_doctor_tip_suppressed_off_linux(monkeypatch, capsys):
    _patch_doctor_report(monkeypatch)
    monkeypatch.setattr(cli, "_desktop_shortcuts_supported", lambda: False)
    # find_gui_binary would otherwise trigger the tip; ensure the gate wins.
    monkeypatch.setattr("headmatch.desktop.find_gui_binary", lambda: "/usr/bin/headmatch-gui")

    cli.main(["doctor"])

    out = capsys.readouterr().out
    assert "create-shortcut" not in out
    assert "Desktop shortcut" not in out
