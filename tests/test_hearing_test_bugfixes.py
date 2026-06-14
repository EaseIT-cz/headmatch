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


def test_intro_instructions_are_ascii_and_cover_volume():
    text = "\n".join(ht_view._INTRO_INSTRUCTIONS)
    assert text.isascii(), "intro instructions must be ASCII-renderable"
    assert "volume" in text.lower(), "intro must guide the user on volume level"


# ── Bug 3: engine always terminates ───────────────────────────────────────────

def test_engine_terminates_when_listener_hears_everything():
    eng = ThresholdEngine(1000)
    for _ in range(500):
        if eng.done:
            break
        eng.record_response(True)
    assert eng.done, "engine must terminate even if every tone is heard"
    # Hearing the floor means the volume is too high to bracket a threshold:
    # the engine flags it floored and reports it undetermined (0.8.3 guards).
    assert eng.floored is True
    assert eng.threshold is None


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
    # Terminates within the safety cap (which doubles as a max-length bound).
    from headmatch.hearing_test import MAX_PRESENTATIONS
    assert n <= MAX_PRESENTATIONS


def test_hearing_fit_graphiceq_point_count_is_sane(tmp_path):
    # Regression: run_hearing_fit used geometric_log_grid(20, 20000, 512) where
    # 512 is points-per-octave -> ~5103 points, which crashed EasyEffects.
    from headmatch.hearing_test import HearingProfile, FrequencyThreshold, TEST_FREQUENCIES
    from headmatch.pipeline import run_hearing_fit

    left = {f: FrequencyThreshold(f, -30.0, 3, True) for f in TEST_FREQUENCIES}
    right = {f: FrequencyThreshold(f, -30.0, 3, True) for f in TEST_FREQUENCIES}
    profile = HearingProfile(left=left, right=right, tested_at="2026-01-01T00:00:00Z", asymmetric_freqs=[])

    run_hearing_fit(profile, str(tmp_path), sample_rate=48000)
    text = (tmp_path / "equalizer_apo_graphiceq.txt").read_text()
    gq_lines = [ln for ln in text.splitlines() if ln.startswith("GraphicEQ:")]
    assert gq_lines, "no GraphicEQ line written"
    n_points = len(gq_lines[0].split(":", 1)[1].split(";"))
    # Standard 127-point grid (AutoEq de-facto), never the ~5103-point grid that
    # crashed EasyEffects.
    assert n_points <= 130, f"GraphicEQ should use the standard grid, got {n_points} points"


def test_deadband_ignores_sub_threshold_losses():
    # Losses below the ~10 dB self-test noise deadband must not produce EQ.
    from headmatch.hearing_test import (
        HearingProfile, FrequencyThreshold, TEST_FREQUENCIES, NORMAL_HEARING_REFERENCE,
        compute_compensation_points,
    )
    side = {f: FrequencyThreshold(f, NORMAL_HEARING_REFERENCE[f] + 8.0, 3, True) for f in TEST_FREQUENCIES}
    profile = HearingProfile(left=dict(side), right=dict(side), tested_at="t", asymmetric_freqs=[])
    assert compute_compensation_points(profile) == {}


def test_lsq_band_gains_realize_target_accounting_for_interaction():
    # The least-squares solve must make the realized chain hit the target gains
    # at the measured frequencies despite overlapping (summing) bands.
    import numpy as np
    from headmatch.hearing_test import (
        HearingProfile, FrequencyThreshold, TEST_FREQUENCIES, NORMAL_HEARING_REFERENCE,
        compute_compensation_points, eq_bands_from_gain_points,
    )
    from headmatch.peq import peq_chain_response_db

    loss = {250: 4, 500: 5, 1000: 8, 2000: 13, 3000: 22, 4000: 32, 6000: 40, 8000: 48}
    side = {f: FrequencyThreshold(f, NORMAL_HEARING_REFERENCE[f] + loss[f], 3, True) for f in TEST_FREQUENCIES}
    profile = HearingProfile(left=dict(side), right=dict(side), tested_at="t", asymmetric_freqs=[])
    points = compute_compensation_points(profile)
    bands = eq_bands_from_gain_points(points, sample_rate=48000)

    freqs = np.array(sorted(points), dtype=float)
    realized = peq_chain_response_db(freqs, 48000, bands)
    for f, r in zip(freqs, realized):
        assert abs(r - points[int(f)]) < 1.0, f"{int(f)} Hz: realized {r:.2f} vs target {points[int(f)]}"


def test_parametric_bands_placed_at_audiometric_frequencies(tmp_path):
    # Direct 7-frequency EQ: peaking filters sit AT the measured frequencies,
    # not at greedy-fit positions on an interpolated grid.
    from headmatch.hearing_test import (
        HearingProfile, FrequencyThreshold, TEST_FREQUENCIES, NORMAL_HEARING_REFERENCE,
        eq_bands_from_gain_points, compute_compensation_points,
    )
    side = {f: FrequencyThreshold(f, NORMAL_HEARING_REFERENCE[f] + 20.0, 3, True) for f in TEST_FREQUENCIES}
    profile = HearingProfile(left=dict(side), right=dict(side), tested_at="t", asymmetric_freqs=[])
    bands = eq_bands_from_gain_points(compute_compensation_points(profile))
    assert bands, "expected boost bands for 20 dB loss"
    assert all(b.kind == "peaking" for b in bands)
    assert all(round(b.freq) in TEST_FREQUENCIES for b in bands)
    # Wider spacing -> lower Q; narrower spacing -> higher Q.
    qs = {round(b.freq): b.q for b in bands}
    assert qs[1000] < qs[4000]
