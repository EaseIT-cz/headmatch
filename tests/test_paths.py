"""Tests for platform-aware config/cache paths."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch


def test_config_dir_linux(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    from headmatch import paths
    import importlib
    importlib.reload(paths)
    d = paths.config_dir()
    assert d == tmp_path / ".config" / "headmatch"
    assert d.exists()


def test_config_dir_linux_xdg(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    from headmatch import paths
    import importlib
    importlib.reload(paths)
    d = paths.config_dir()
    assert d == tmp_path / "xdg" / "headmatch"


def test_config_dir_darwin(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.platform", "darwin")
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    from headmatch import paths
    import importlib
    importlib.reload(paths)
    d = paths.config_dir()
    assert d == tmp_path / "Library" / "Application Support" / "headmatch"
    assert d.exists()


def test_config_dir_win32(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData"))
    from headmatch import paths
    import importlib
    importlib.reload(paths)
    d = paths.config_dir()
    assert d == tmp_path / "AppData" / "headmatch"


def test_cache_dir_linux(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    from headmatch import paths
    import importlib
    importlib.reload(paths)
    d = paths.cache_dir()
    assert d == tmp_path / ".cache" / "headmatch"
    assert d.exists()


def test_cache_dir_darwin(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.platform", "darwin")
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    from headmatch import paths
    import importlib
    importlib.reload(paths)
    d = paths.cache_dir()
    assert d == tmp_path / "Library" / "Caches" / "headmatch"
    assert d.exists()


def test_cache_dir_win32(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    from headmatch import paths
    import importlib
    importlib.reload(paths)
    d = paths.cache_dir()
    assert d == tmp_path / "Local" / "headmatch" / "cache"


def test_cache_dir_fallback_on_oserror(tmp_path, monkeypatch):
    """If primary cache dir can't be created, falls back to tempdir."""
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setattr("pathlib.Path.home", lambda: Path("/nonexistent/fakehome"))
    from headmatch import paths
    import importlib
    importlib.reload(paths)
    d = paths.cache_dir()
    assert "headmatch" in str(d)
    assert d.exists()
