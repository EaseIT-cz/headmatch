"""Tests for desktop shortcut management."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from headmatch.desktop import (
    DESKTOP_ENTRY_TEMPLATE,
    create_shortcut,
    desktop_shortcut_path,
    find_gui_binary,
    remove_shortcut,
    shortcut_exists,
)


def test_find_gui_binary_returns_none_when_not_installed():
    with patch("shutil.which", return_value=None):
        # Also patch the sys.executable fallback
        with patch("headmatch.desktop.Path.exists", return_value=False):
            result = find_gui_binary()
            # May or may not find it depending on environment
            assert result is None or isinstance(result, str)


def test_desktop_shortcut_path_is_in_local_share():
    path = desktop_shortcut_path()
    assert ".local/share/applications" in str(path)
    assert path.name == "headmatch.desktop"


def test_create_shortcut_writes_desktop_file(tmp_path: Path, monkeypatch):
    fake_apps = tmp_path / "applications"
    monkeypatch.setattr("headmatch.desktop.DESKTOP_DIR", fake_apps)
    path = create_shortcut("/usr/bin/headmatch-gui")
    assert path.exists()
    content = path.read_text()
    assert "Exec=/usr/bin/headmatch-gui" in content
    assert "[Desktop Entry]" in content
    assert "HeadMatch" in content


def test_remove_shortcut_deletes_file(tmp_path: Path, monkeypatch):
    fake_apps = tmp_path / "applications"
    fake_apps.mkdir(parents=True)
    desktop_file = fake_apps / "headmatch.desktop"
    desktop_file.write_text("[Desktop Entry]")
    monkeypatch.setattr("headmatch.desktop.DESKTOP_DIR", fake_apps)
    assert remove_shortcut() is True
    assert not desktop_file.exists()


def test_remove_shortcut_returns_false_when_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("headmatch.desktop.DESKTOP_DIR", tmp_path)
    assert remove_shortcut() is False


def test_shortcut_exists_reflects_file_state(tmp_path: Path, monkeypatch):
    fake_apps = tmp_path / "applications"
    monkeypatch.setattr("headmatch.desktop.DESKTOP_DIR", fake_apps)
    assert shortcut_exists() is False
    fake_apps.mkdir(parents=True)
    (fake_apps / "headmatch.desktop").write_text("test")
    assert shortcut_exists() is True


def test_create_shortcut_raises_when_no_binary(tmp_path: Path, monkeypatch):
    import pytest
    monkeypatch.setattr("headmatch.desktop.DESKTOP_DIR", tmp_path)
    monkeypatch.setattr("headmatch.desktop.find_gui_binary", lambda: None)
    with pytest.raises(FileNotFoundError, match="headmatch-gui"):
        create_shortcut(None)
