"""Tests for headmatch.utils module."""

from __future__ import annotations

from pathlib import Path

import pytest

from headmatch.utils import (
    expanded_parent,
    expanded_dir,
    ensure_parent_exists,
    sanitize_filename,
    ImmediateThread,
    SyncQueue,
)


class TestPathHelpers:
    """Tests for path expansion utilities."""

    def test_expanded_parent_returns_parent_of_value(self, tmp_path):
        result = expanded_parent(str(tmp_path / "sub" / "file.csv"), tmp_path)
        assert result == str(tmp_path / "sub")

    def test_expanded_parent_returns_fallback_when_value_empty(self, tmp_path):
        result = expanded_parent("", tmp_path / "fallback")
        assert result == str(tmp_path / "fallback")

    def test_expanded_parent_returns_fallback_when_value_whitespace(self, tmp_path):
        result = expanded_parent("   ", tmp_path / "fallback")
        assert result == str(tmp_path / "fallback")

    def test_expanded_parent_expands_tilde(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        result = expanded_parent("~/file.csv", "/fallback")
        # Just check it doesn't literally contain ~
        assert "~" not in result

    def test_expanded_dir_returns_value_expanded(self, tmp_path):
        result = expanded_dir(str(tmp_path / "output"), tmp_path / "fallback")
        assert result == str(tmp_path / "output")

    def test_expanded_dir_returns_fallback_when_empty(self, tmp_path):
        result = expanded_dir("", tmp_path / "fallback")
        assert result == str(tmp_path / "fallback")

    def test_expanded_dir_expands_tilde(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        result = expanded_dir("~/output", "/fallback")
        assert "~" not in result

    def test_ensure_parent_exists_creates_directory(self, tmp_path):
        target = tmp_path / "deeply" / "nested" / "output.csv"
        result = ensure_parent_exists(target)
        assert result == Path(target).expanduser()
        assert (tmp_path / "deeply" / "nested").exists()

    def test_ensure_parent_exists_handles_existing_dir(self, tmp_path):
        target = tmp_path / "existing" / "file.txt"
        (tmp_path / "existing").mkdir()
        result = ensure_parent_exists(target)
        assert result == Path(target).expanduser()

    def test_sanitize_filename_replaces_slashes(self):
        assert sanitize_filename("path/to/file") == "path_to_file"
        assert sanitize_filename("path\\to\\file") == "path_to_file"
        assert sanitize_filename("mixed/path\\name") == "mixed_path_name"

    def test_sanitize_filename_preserves_normal_names(self):
        assert sanitize_filename("normal_file.csv") == "normal_file.csv"
        assert sanitize_filename("HD 650") == "HD 650"


class TestImmediateThread:
    """Tests for ImmediateThread test double."""

    def test_runs_target_immediately(self):
        calls = []
        thread = ImmediateThread(
            target=lambda: calls.append("ran"),
            daemon=True
        )
        assert calls == []
        thread.start()
        assert calls == ["ran"]

    def test_runs_target_that_raises(self):
        def boom():
            raise RuntimeError("boom")
        
        thread = ImmediateThread(target=boom, daemon=True)
        # Should not raise - exceptions propagate from start()
        with pytest.raises(RuntimeError, match="boom"):
            thread.start()

    def test_daemon_attribute_stored(self):
        thread = ImmediateThread(target=lambda: None, daemon=False)
        assert thread.daemon is False


class TestSyncQueue:
    """Tests for SyncQueue test utility."""

    def test_put_and_get_event(self):
        q = SyncQueue()
        q.put(("success", 42))
        event = q.get_event()
        assert event == "success"
        assert q.get_payload() == 42

    def test_get_event_consumes_item(self):
        q = SyncQueue([("success", 123)])
        q.get_event()
        assert q.is_empty()

    def test_is_empty_returns_false_when_has_items(self):
        q = SyncQueue([("success", 1)])
        assert q.is_empty() is False

    def test_is_empty_returns_true_when_empty(self):
        q = SyncQueue()
        assert q.is_empty() is True

    def test_pre_populated_items(self):
        q = SyncQueue([("error", RuntimeError("boom")), ("success", 42)])
        assert q.get_event() == "error"
        assert q.get_event() == "success"

    def test_get_nowait_raises_empty(self):
        import queue
        q = SyncQueue()
        with pytest.raises(queue.Empty):
            q.get_nowait()
