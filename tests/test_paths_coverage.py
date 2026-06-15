"""Coverage tests for paths.py missing lines.

Targets: 50-59 (documents_dir on win32 and non-win32).
"""
from __future__ import annotations

import importlib
from pathlib import Path


def test_documents_dir_linux(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    from headmatch import paths

    importlib.reload(paths)
    d = paths.documents_dir()
    assert d == tmp_path / "Documents" / "HeadMatch"
    assert d.exists()


def test_documents_dir_darwin(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.platform", "darwin")
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    from headmatch import paths

    importlib.reload(paths)
    d = paths.documents_dir()
    assert d == tmp_path / "Documents" / "HeadMatch"
    assert d.exists()


def test_documents_dir_win32_with_userprofile(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "profile"))
    from headmatch import paths

    importlib.reload(paths)
    d = paths.documents_dir()
    assert d == tmp_path / "profile" / "Documents" / "HeadMatch"
    assert d.exists()


def test_documents_dir_win32_without_userprofile(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.delenv("USERPROFILE", raising=False)
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    from headmatch import paths

    importlib.reload(paths)
    d = paths.documents_dir()
    assert d == tmp_path / "Documents" / "HeadMatch"
    assert d.exists()
