from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolate_user_config_dirs(monkeypatch, tmp_path):
    sandbox_home = tmp_path / "home"
    sandbox_xdg = tmp_path / "xdg-config"
    sandbox_home.mkdir()
    sandbox_xdg.mkdir()
    monkeypatch.setenv("HOME", str(sandbox_home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(sandbox_xdg))
