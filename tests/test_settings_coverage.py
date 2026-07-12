"""Coverage tests for settings.py missing lines.

Targets: 48, 51-52, 54, 74-75, 97.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from headmatch.contracts import FrontendConfig
from headmatch.exceptions import ConfigError
from headmatch.settings import (
    load_config,
    load_or_create_config,
    update_config_from_args,
)


# ── line 48: load_config returns default when file is missing ──

def test_load_config_missing_returns_default(tmp_path):
    config = load_config(tmp_path / "does_not_exist.json")
    assert isinstance(config, FrontendConfig)


# ── lines 51-52: invalid JSON raises ValueError ──

def test_load_config_invalid_json(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ConfigError, match="Invalid JSON in config file"):
        load_config(path)


# ── line 54: JSON that is not an object ──

def test_load_config_non_object_json(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    with pytest.raises(ConfigError, match="must contain a JSON object"):
        load_config(path)


# ── lines 74-75: load_or_create_config swallows OSError on save ──

def test_load_or_create_config_save_oserror(tmp_path, monkeypatch):
    target = tmp_path / "config.json"

    def boom(config, path):
        raise OSError("read-only filesystem")

    monkeypatch.setattr("headmatch.settings.save_config", boom)
    config, path, created = load_or_create_config(target)
    assert isinstance(config, FrontendConfig)
    assert path == target
    assert created is False


def test_load_or_create_config_creates_when_missing(tmp_path):
    target = tmp_path / "new" / "config.json"
    config, path, created = load_or_create_config(target)
    assert created is True
    assert target.exists()


def test_load_or_create_config_existing(tmp_path):
    target = tmp_path / "config.json"
    target.write_text(json.dumps({"sample_rate": 44100}), encoding="utf-8")
    config, path, created = load_or_create_config(target)
    assert created is False
    assert config.sample_rate == 44100


# ── line 97: update_config_from_args iterate branch ──

def test_update_config_from_args_iterate_branch():
    args = SimpleNamespace(cmd="iterate", iterations=7)
    config = update_config_from_args(args, existing=FrontendConfig())
    assert config.iterate_iterations == 7


def test_update_config_from_args_start_branch():
    args = SimpleNamespace(cmd="start", iterations=4)
    config = update_config_from_args(args, existing=FrontendConfig())
    assert config.start_iterations == 4
