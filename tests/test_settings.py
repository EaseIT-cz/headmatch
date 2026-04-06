from __future__ import annotations

import sys

import pytest

from argparse import Namespace

from headmatch.contracts import FrontendConfig
from tests.config_fixtures import varied_config
from headmatch.settings import (
    default_config_path,
    load_config,
    load_or_create_config,
    save_config,
    update_config_from_args,
)


@pytest.mark.skipif(sys.platform != "linux", reason="XDG is Linux-only")
def test_default_config_path_prefers_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert default_config_path() == tmp_path / "xdg" / "headmatch" / "config.json"


def test_load_or_create_config_writes_safe_defaults(tmp_path):
    path = tmp_path / "config.json"
    config, created_path, created = load_or_create_config(path)

    assert created is True
    assert created_path == path
    assert path.exists()
    assert config.sample_rate == 48000
    assert config.max_filters == 8
    assert config.pipewire_input_target is None
    assert config.pipewire_output_target is None


def test_load_config_ignores_unknown_keys(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"sample_rate": 44100, "unknown": 1}')

    config = load_config(path)

    assert config.sample_rate == 44100
    assert not hasattr(config, "unknown")


def test_update_config_from_args_keeps_explicit_cli_values():
    config = FrontendConfig(pipewire_output_target="saved-out", pipewire_input_target="saved-in")
    args = Namespace(
        cmd="measure",
        out_dir="out/run_01",
        target_csv=None,
        output_target="cli-out",
        input_target="cli-in",
        sample_rate=44100,
        duration=6.0,
        f_start=30.0,
        f_end=20000.0,
        pre_silence=0.3,
        post_silence=0.7,
        amplitude=0.15,
        max_filters=6,
        iterations=None,
    )

    updated = update_config_from_args(args, existing=config)

    assert updated.default_output_dir == "out/run_01"
    assert updated.pipewire_output_target == "cli-out"
    assert updated.pipewire_input_target == "cli-in"
    assert updated.sample_rate == 44100
    assert updated.max_filters == 6


def test_save_and_load_round_trip(tmp_path):
    path = tmp_path / "config.json"
    _suffix, original = varied_config(suffix="17cafefeed42abcd99aa99aa")

    save_config(original, path)
    loaded = load_config(path)

    assert loaded == original
