"""Tests for the headless CLI hearing-test runner (run_cli_hearing_test).

This is the `headmatch hearing-test` driver and was previously uncovered. The
real Hughson-Westlake staircase is exercised in test_hearing_test.py; here a
fake engine that converges after a fixed number of responses keeps the I/O
orchestration test deterministic (the real engine never terminates on
all-misses).
"""
from __future__ import annotations

import io
import sys

from headmatch import hearing_test as ht_mod
from headmatch.hearing_test import HearingProfile, TEST_FREQUENCIES, run_cli_hearing_test


class _FakeEngine:
    def __init__(self, freq_hz, start_level_dbfs=-20.0):
        self.freq_hz = freq_hz
        self.current_level_dbfs = start_level_dbfs
        self._n = 0
        self.done = False
        self.threshold = -45.0
        self.ascending_run_count = 2

    def record_response(self, _heard):
        self._n += 1
        if self._n >= 2:
            self.done = True


class _FakeBackend:
    def __init__(self):
        self.calls = 0

    def play_tone(self, *a, **k):
        self.calls += 1


def _patch_fast(monkeypatch):
    monkeypatch.setattr(ht_mod, "ThresholdEngine", _FakeEngine)
    monkeypatch.setattr(ht_mod, "RESPONSE_WINDOW_S", 0.01)
    monkeypatch.setattr(ht_mod, "generate_tone", lambda *a, **k: [0.0])
    monkeypatch.setattr("builtins.input", lambda *a, **k: "")
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))


def test_returns_complete_profile_for_both_ears(monkeypatch):
    _patch_fast(monkeypatch)
    backend = _FakeBackend()
    statuses: list[str] = []

    profile = run_cli_hearing_test(backend, None, 48000, on_status=statuses.append)

    assert isinstance(profile, HearingProfile)
    assert set(profile.left) == set(TEST_FREQUENCIES)
    assert set(profile.right) == set(TEST_FREQUENCIES)
    assert all(t.determined for t in profile.left.values())
    assert backend.calls > 0          # tones were actually played
    assert statuses                   # on_status callback path exercised
    assert isinstance(profile.asymmetric_freqs, list)


def test_default_status_prints_to_stdout(monkeypatch, capsys):
    _patch_fast(monkeypatch)
    # No on_status -> the runner prints instructions itself.
    run_cli_hearing_test(_FakeBackend(), None)
    out = capsys.readouterr().out
    assert "Hearing Threshold Test" in out
