"""End-to-end test of the hearing-test -> hearing-fit inter-command contract.

This proves that a hearing profile *written* by the ``headmatch hearing-test``
CLI command is correctly *read* and consumed by the ``headmatch hearing-fit``
CLI command to produce a compensation EQ. Both commands are driven through the
real ``cli.main([...])`` entry point in the same test, so the file that
hearing-fit loads is exactly the one hearing-test persisted (the conftest
autouse fixture sandboxes HOME/XDG_CONFIG_HOME, so the config-dir profile
survives between the two cli.main calls).

Chosen seam (and why)
---------------------
The interactive runner ``run_cli_hearing_test`` obtains each per-frequency
threshold from ``hearing_test.ThresholdEngine`` (a Hughson-Westlake staircase
driven by tone playback + Enter-press responses). Rather than mock playback,
stdin, timers, AND choreograph a heard/not-heard response sequence that makes
the *real* engine converge on a chosen level per frequency (brittle and
frequency-coupled), we monkeypatch the single seam the CLI uses to obtain a
threshold: ``ThresholdEngine``. Our fake engine reports, for each frequency, a
threshold equal to ``NORMAL_HEARING_REFERENCE[f] + presbycusis_loss[f]`` and
converges on the first response. This still exercises the genuine CLI
profile-WRITE path end to end -- ``run_cli_hearing_test`` orchestration,
``averaged_frequency_threshold``, ``HearingProfile`` assembly, and
``save_hearing_profile`` to ``hearing_profile_path()`` -- without real audio,
stdin, or home. We additionally neutralise tone generation, the response
window, sleeps, stdin and catch trials so the run is deterministic and fast.

The contract crux: the profile is NEVER written via the API in this test. It is
produced solely by the hearing-test CLI run, and hearing-fit reads it back via
its own CLI run (``load_hearing_profile``).
"""
from __future__ import annotations

import io
import json
import sys

import pytest

from headmatch import cli
from headmatch import hearing_test as ht_mod
from headmatch.hearing_test import (
    MAX_COMPENSATION_DB,
    NORMAL_HEARING_REFERENCE,
    TEST_FREQUENCIES,
    hearing_profile_path,
)


# A representative middle-aged (presbycusis) audiogram, mirroring
# tests/test_e2e_fitting.py: gentle low-frequency loss sloping to a moderate
# high-frequency loss (dB above the normal reference).
_PRESBYCUSIS_LOSS_DB = {250: 4, 500: 5, 1000: 8, 2000: 13, 3000: 22, 4000: 32, 6000: 40, 8000: 48}


class _PresbycusisEngine:
    """Stand-in for ht_mod.ThresholdEngine that converges immediately on a
    presbycusis threshold for its frequency.

    The runner constructs it as ``ThresholdEngine(freq_hz, start_level_dbfs=...)``,
    plays a tone, calls ``record_response(heard)`` until ``done``, then reads
    ``threshold`` / ``converged`` / ``floored`` / ``ascending_run_count``.
    Louder (less negative dBFS) threshold == worse hearing, so high frequencies
    get the larger loss and therefore the higher (worse) threshold.
    """

    def __init__(self, freq_hz, start_level_dbfs=-20.0):
        self.freq_hz = freq_hz
        loss = _PRESBYCUSIS_LOSS_DB.get(freq_hz, 0.0)
        self._threshold = NORMAL_HEARING_REFERENCE[freq_hz] + loss
        self.current_level_dbfs = self._threshold
        self.threshold = self._threshold
        self.ascending_run_count = 3
        self.converged = True
        self.floored = False
        self.done = False

    def record_response(self, _heard):
        # Converge on the first presentation; no real staircase needed.
        self.done = True


class _SilentBackend:
    """Audio backend stub: counts play_tone calls, emits nothing."""

    def __init__(self):
        self.calls = 0

    def play_tone(self, *a, **k):
        self.calls += 1


@pytest.fixture
def patched_hearing_test(monkeypatch):
    """Make cli.main(["hearing-test", ...]) deterministic and audio/stdin-free
    while still exercising the genuine profile-write path."""
    monkeypatch.setattr(ht_mod, "ThresholdEngine", _PresbycusisEngine)
    # No real synthesis, no real audio device.
    monkeypatch.setattr(ht_mod, "generate_tone_train", lambda *a, **k: [0.0])
    monkeypatch.setattr(ht_mod, "generate_silence", lambda *a, **k: [0.0])
    monkeypatch.setattr(
        "headmatch.audio_backend.get_audio_backend", lambda *a, **k: _SilentBackend()
    )
    # No waiting: zero response window, no jitter sleeps, never insert catches.
    monkeypatch.setattr(ht_mod, "RESPONSE_WINDOW_S", 0.0)
    monkeypatch.setattr(ht_mod.time, "sleep", lambda *_: None)
    monkeypatch.setattr(ht_mod, "should_insert_catch", lambda *a, **k: False)
    # No interactive stdin.
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    monkeypatch.setattr("builtins.input", lambda *a, **k: "")


def test_hearing_test_cli_writes_presbycusis_profile(patched_hearing_test):
    """Step 1: the hearing-test CLI writes a profile reflecting the simulated
    sloping high-frequency loss."""
    profile_path = hearing_profile_path()
    assert not profile_path.exists()

    rc = cli.main(["hearing-test"])
    assert rc in (0, None)

    # The CLI persisted a profile file at the canonical config-dir location.
    assert profile_path.exists(), f"hearing-test did not write {profile_path}"

    saved = json.loads(profile_path.read_text(encoding="utf-8"))
    left = {int(f): t["level_dbfs"] for f, t in saved["left"].items()}
    # Every tested frequency was determined.
    assert set(left) == set(TEST_FREQUENCIES)
    # High-frequency threshold is worse (louder / less negative dBFS) than low.
    assert left[8000] > left[250], (
        f"expected sloping HF loss: 8 kHz {left[8000]} should be worse than 250 Hz {left[250]}"
    )
    # Monotone-ish slope: 4 kHz worse than 1 kHz too.
    assert left[4000] > left[1000]


def test_hearing_fit_cli_consumes_profile_and_boosts_high_frequencies(
    patched_hearing_test, tmp_path
):
    """Steps 1-3 (the full contract): hearing-test writes the profile, then
    hearing-fit -- WITHOUT recreating it -- loads that very file and produces a
    high-frequency-weighted compensation EQ within the compensation cap."""
    # --- Step 1: hearing-test CLI writes the profile. ---
    assert cli.main(["hearing-test"]) in (0, None)
    profile_path = hearing_profile_path()
    assert profile_path.exists()
    written_bytes = profile_path.read_bytes()

    # --- Step 2 & 3: hearing-fit CLI reads it back (no API write here). ---
    out_dir = tmp_path / "hearing_fit_out"
    rc = cli.main(["hearing-fit", "--out-dir", str(out_dir)])
    assert rc in (0, None)

    # hearing-fit must not have rewritten the source profile -- it only reads it.
    assert profile_path.read_bytes() == written_bytes

    # All expected EQ artifacts written by hearing-fit.
    for name in ("equalizer_apo.txt", "equalizer_apo_graphiceq.txt", "hearing_fit_report.json"):
        assert (out_dir / name).exists(), f"hearing-fit did not write {name}"

    report = json.loads((out_dir / "hearing_fit_report.json").read_text(encoding="utf-8"))
    assert report["mode"] == "hearing_only"
    bands = report["left_bands"]
    assert bands, "expected compensation bands for presbycusis"

    by_freq = {round(b["freq"]): b["gain_db"] for b in bands}
    # Compensation boosts high frequencies more than low (sloping loss).
    assert max(by_freq) >= 6000
    assert by_freq[max(by_freq)] > by_freq[min(by_freq)], (
        f"expected HF boost > LF boost, got {by_freq}"
    )
    # All gains respect the compensation cap.
    assert all(b["gain_db"] <= MAX_COMPENSATION_DB + 1e-6 for b in bands)

    # Record the observed high-vs-low boost for the test report.
    print(
        f"hearing-fit boost: low {by_freq[min(by_freq)]:.2f} dB @ {min(by_freq)} Hz, "
        f"high {by_freq[max(by_freq)]:.2f} dB @ {max(by_freq)} Hz"
    )
