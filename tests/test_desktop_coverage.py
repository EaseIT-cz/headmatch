"""Coverage tests for desktop.py missing lines.

Targets: 31 (which finds the binary), 35 (fallback candidate exists).
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from headmatch.desktop import find_gui_binary


# ── line 31: shutil.which finds the binary ──

def test_find_gui_binary_via_which():
    with patch("shutil.which", return_value="/usr/local/bin/headmatch-gui"):
        assert find_gui_binary() == "/usr/local/bin/headmatch-gui"


# ── line 35: which misses, but the sibling-of-python candidate exists ──

def test_find_gui_binary_via_executable_fallback(tmp_path, monkeypatch):
    fake_bin = tmp_path / "headmatch-gui"
    fake_bin.write_text("#!/bin/sh\n")
    fake_python = tmp_path / "python"
    monkeypatch.setattr("headmatch.desktop.sys.executable", str(fake_python))
    with patch("shutil.which", return_value=None):
        result = find_gui_binary()
    assert result == str(fake_bin)
