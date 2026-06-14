"""Regression tests for three hearing-test bugs reported against 0.8.2.

1. Tone played in both ears while testing a single ear (generate_tone always
   duplicated the mono signal into both channels).
2. Non-ASCII status glyphs (♪ ✓ — …) failed to render in the user's Tk font.
3. The threshold engine never terminated when the listener heard (or missed)
   every presentation — the test got stuck on the first frequency.
"""
from __future__ import annotations

import numpy as np

from headmatch.hearing_test import ThresholdEngine, generate_tone
from headmatch.gui.views import hearing_test as ht_view


# ── Bug 1: per-ear channel routing ────────────────────────────────────────────

def test_generate_tone_left_silences_right_channel():
    buf = generate_tone(1000, -20.0, 48000, ear="left")
    assert buf.shape[1] == 2
    assert np.any(buf[:, 0] != 0.0), "left channel should carry the tone"
    assert np.all(buf[:, 1] == 0.0), "right channel must be silent for left ear"


def test_generate_tone_right_silences_left_channel():
    buf = generate_tone(1000, -20.0, 48000, ear="right")
    assert np.all(buf[:, 0] == 0.0), "left channel must be silent for right ear"
    assert np.any(buf[:, 1] != 0.0), "right channel should carry the tone"


def test_generate_tone_both_ears_is_default():
    buf = generate_tone(1000, -20.0, 48000)
    assert np.array_equal(buf[:, 0], buf[:, 1])
    assert np.any(buf[:, 0] != 0.0)


# ── Bug 2: ASCII-only status strings ──────────────────────────────────────────

def test_speaker_status_strings_are_ascii():
    for s in (ht_view._STATUS_PLAYING, ht_view._STATUS_HEARD, ht_view._STATUS_NOT_HEARD):
        assert s.isascii(), f"status string must be ASCII-renderable: {s!r}"


# ── Bug 3: engine always terminates ───────────────────────────────────────────

def test_engine_terminates_when_listener_hears_everything():
    eng = ThresholdEngine(1000)
    for _ in range(500):
        if eng.done:
            break
        eng.record_response(True)
    assert eng.done, "engine must terminate even if every tone is heard"
    # Heard even the quietest tone -> threshold determined at/near the floor.
    assert eng.threshold is not None


def test_engine_terminates_when_listener_misses_everything():
    eng = ThresholdEngine(1000)
    for _ in range(500):
        if eng.done:
            break
        eng.record_response(False)
    assert eng.done, "engine must terminate even if every tone is missed"
    # Never heard anything -> threshold genuinely undetermined.
    assert eng.threshold is None


def test_engine_still_converges_normally_within_cap():
    # A realistic responder (heard at/above -45 dBFS) must converge well before
    # the safety cap and not be cut short by it.
    eng = ThresholdEngine(1000)
    n = 0
    while not eng.done and n < 500:
        eng.record_response(eng.current_level_dbfs >= -45.0)
        n += 1
    assert eng.done
    assert eng.threshold == -45.0
