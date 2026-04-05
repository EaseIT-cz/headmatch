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


# ── Config field aliasing tests (TASK-089) ──

def test_config_new_field_names_loaded(tmp_path):
    """Config JSON with output_target/input_target should load correctly."""
    import json
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({
        "output_target": "my-dac",
        "input_target": "my-mic",
    }))
    from headmatch.settings import load_config
    config = load_config(config_file)
    assert config.pipewire_output_target == "my-dac"
    assert config.pipewire_input_target == "my-mic"
    assert config.output_target == "my-dac"
    assert config.input_target == "my-mic"


def test_config_old_field_names_still_work(tmp_path):
    """Config JSON with pipewire_output_target should still load."""
    import json
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({
        "pipewire_output_target": "old-dac",
        "pipewire_input_target": "old-mic",
    }))
    from headmatch.settings import load_config
    config = load_config(config_file)
    assert config.output_target == "old-dac"
    assert config.input_target == "old-mic"


def test_config_old_names_take_precedence(tmp_path):
    """If both old and new names exist, old (canonical) wins."""
    import json
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({
        "pipewire_output_target": "canonical-dac",
        "output_target": "alias-dac",
    }))
    from headmatch.settings import load_config
    config = load_config(config_file)
    assert config.output_target == "canonical-dac"


def test_config_property_setter():
    """Setting output_target property should update pipewire_output_target."""
    from headmatch.contracts import FrontendConfig
    config = FrontendConfig()
    config.output_target = "new-dac"
    assert config.pipewire_output_target == "new-dac"
    config.input_target = "new-mic"
    assert config.pipewire_input_target == "new-mic"


def test_config_serializes_with_new_field_names():
    """to_dict() should use output_target, not pipewire_output_target."""
    from headmatch.contracts import FrontendConfig
    config = FrontendConfig(pipewire_output_target="dac", pipewire_input_target="mic")
    d = config.to_dict()
    assert "output_target" in d
    assert "input_target" in d
    assert "pipewire_output_target" not in d
    assert "pipewire_input_target" not in d
    assert d["output_target"] == "dac"
    assert d["input_target"] == "mic"


def test_config_round_trip_through_new_names(tmp_path):
    """Save with new names, load back, verify values."""
    from headmatch.contracts import FrontendConfig
    from headmatch.settings import save_config, load_config
    config = FrontendConfig(pipewire_output_target="my-dac", pipewire_input_target="my-mic")
    path = save_config(config, tmp_path / "config.json")
    reloaded = load_config(path)
    assert reloaded.output_target == "my-dac"
    assert reloaded.input_target == "my-mic"
