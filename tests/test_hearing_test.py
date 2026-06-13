"""Tests for the hearing threshold engine and tone generation."""
from __future__ import annotations

import json

import numpy as np
import pytest

from headmatch.hearing_test import (
    GAIN_FRACTION,
    MAX_ASCENDING_RUNS,
    MAX_COMPENSATION_DB,
    NORMAL_HEARING_REFERENCE,
    RAMP_DURATION_S,
    START_LEVEL_DBFS,
    STEP_DOWN_DB,
    STEP_UP_DB,
    TEST_FREQUENCIES,
    TEST_ORDER,
    TONE_DURATION_S,
    FrequencyThreshold,
    HearingProfile,
    ThresholdEngine,
    compute_compensation_curve,
    detect_asymmetric_frequencies,
    generate_tone,
    load_hearing_profile,
    save_hearing_profile,
)
from headmatch.signals import geometric_log_grid


# ── ThresholdEngine ───────────────────────────────────────────────────────────

class TestThresholdEngine:
    def test_starts_at_start_level(self):
        e = ThresholdEngine(1000)
        assert e.current_level_dbfs == START_LEVEL_DBFS

    def test_step_down_after_heard(self):
        e = ThresholdEngine(1000)
        level_before = e.current_level_dbfs
        e.record_response(True)
        assert e.current_level_dbfs == pytest.approx(level_before - STEP_DOWN_DB)

    def test_step_up_after_miss(self):
        e = ThresholdEngine(1000)
        e.record_response(True)  # step down first
        level_before = e.current_level_dbfs
        e.record_response(False)
        assert e.current_level_dbfs == pytest.approx(level_before + STEP_UP_DB)

    def test_stable_threshold_at_same_level_3_times(self):
        e = ThresholdEngine(1000, start_level_dbfs=-30.0)
        # Drive to a stable threshold: simulate a perfect listener at -50 dBFS
        target = -50.0
        for _ in range(20):
            if e.done:
                break
            heard = e.current_level_dbfs >= target
            e.record_response(heard)
        assert e.done
        assert e.threshold is not None
        # Threshold should be at or near target within step resolution
        assert e.threshold <= target + STEP_UP_DB + 1.0

    def test_threshold_not_declared_before_3_ascending_runs(self):
        e = ThresholdEngine(1000, start_level_dbfs=-30.0)
        # Manually drive 2 ascending runs at same level
        # Simulate: hear → down → miss → up → hear (run 1) → down → miss → up → hear (run 2)
        e.record_response(True)    # hear at -30; step down to -40; not ascending
        e.record_response(False)   # miss at -40; step up to -35; ascending
        e.record_response(True)    # hear at -35; run 1; step down to -45
        assert not e.done
        e.record_response(False)   # miss at -45; step up to -40
        e.record_response(True)    # hear at -40; run 2; step down to -50
        assert not e.done  # need 3 runs minimum

    def test_max_runs_terminates(self):
        e = ThresholdEngine(1000, start_level_dbfs=-30.0)
        # Force MAX_ASCENDING_RUNS by always hearing at different levels
        level = -30.0
        for _ in range(MAX_ASCENDING_RUNS * 3):
            if e.done:
                break
            # Alternate miss/hear to keep ascending run count rising
            e.record_response(False)
            if e.done:
                break
            e.record_response(True)
        assert e.done

    def test_not_done_initially(self):
        e = ThresholdEngine(1000)
        assert not e.done

    def test_ascending_run_count_increments(self):
        e = ThresholdEngine(1000, start_level_dbfs=-30.0)
        e.record_response(True)   # not ascending
        e.record_response(False)  # ascending
        e.record_response(True)   # ascending run 1
        assert e.ascending_run_count == 1

    def test_record_after_done_is_noop(self):
        e = ThresholdEngine(1000, start_level_dbfs=-30.0)
        target = -50.0
        for _ in range(30):
            if e.done:
                break
            e.record_response(e.current_level_dbfs >= target)
        assert e.done
        level_after = e.current_level_dbfs
        threshold_after = e.threshold
        e.record_response(True)
        assert e.current_level_dbfs == level_after
        assert e.threshold == threshold_after


# ── generate_tone ─────────────────────────────────────────────────────────────

class TestGenerateTone:
    def test_shape_is_stereo(self):
        samples = generate_tone(1000, -20.0, sample_rate=48000)
        expected_n = int(round(TONE_DURATION_S * 48000))
        assert samples.shape == (expected_n, 2)

    def test_dtype_is_float64(self):
        samples = generate_tone(1000, -20.0)
        assert samples.dtype == np.float64

    def test_level_scales_rms(self):
        samples_loud = generate_tone(1000, -6.0, sample_rate=48000)
        samples_quiet = generate_tone(1000, -20.0, sample_rate=48000)
        rms_loud = np.sqrt(np.mean(samples_loud ** 2))
        rms_quiet = np.sqrt(np.mean(samples_quiet ** 2))
        # 14 dB difference expected (within 1 dB due to ramps)
        ratio_db = 20 * np.log10(rms_loud / rms_quiet)
        assert abs(ratio_db - 14.0) < 1.5

    def test_ramps_reduce_clicks(self):
        samples = generate_tone(1000, -6.0, sample_rate=48000)
        n_ramp = int(round(RAMP_DURATION_S * 48000))
        # First and last sample should be near zero (ramp effect)
        assert abs(float(samples[0, 0])) < 0.001
        assert abs(float(samples[-1, 0])) < 0.001

    def test_channels_are_identical(self):
        samples = generate_tone(2000, -30.0)
        np.testing.assert_array_equal(samples[:, 0], samples[:, 1])

    def test_frequency_content(self):
        sr = 48000
        samples = generate_tone(1000, -6.0, sample_rate=sr)
        mono = samples[:, 0]
        fft = np.abs(np.fft.rfft(mono))
        freqs = np.fft.rfftfreq(len(mono), d=1.0 / sr)
        peak_freq = freqs[np.argmax(fft)]
        # Peak should be within a few Hz of 1000 Hz
        assert abs(peak_freq - 1000.0) < 20.0


# ── compute_compensation_curve ────────────────────────────────────────────────

def _make_profile(thresholds_dbfs: dict[int, float]) -> HearingProfile:
    """Helper: build a symmetric HearingProfile from a freq→level dict."""
    side = {
        f: FrequencyThreshold(freq_hz=f, level_dbfs=t, ascending_runs=3, determined=True)
        for f, t in thresholds_dbfs.items()
    }
    return HearingProfile(left=dict(side), right=dict(side), tested_at="2026-01-01T00:00:00+00:00", asymmetric_freqs=[])


class TestComputeCompensationCurve:
    def _grid(self):
        return geometric_log_grid(100.0, 20000.0, 48)

    def test_flat_at_reference_gives_zero_gain(self):
        """A person with normal hearing (thresholds at reference) gets 0 dB compensation."""
        grid = self._grid()
        profile = _make_profile(NORMAL_HEARING_REFERENCE)
        comp = compute_compensation_curve(profile, grid)
        assert np.all(comp >= 0.0)
        assert np.max(comp) < 0.5  # near zero

    def test_20dB_loss_gives_10dB_gain(self):
        """Half-gain rule: 20 dB of loss → 10 dB of gain."""
        grid = self._grid()
        thresholds = {f: NORMAL_HEARING_REFERENCE[f] + 20.0 for f in TEST_FREQUENCIES}
        profile = _make_profile(thresholds)
        comp = compute_compensation_curve(profile, grid)
        # Near 1-4 kHz the compensation should be around 10 dB
        mask = (grid >= 1000) & (grid <= 4000)
        avg_in_band = float(np.mean(comp[mask]))
        assert 7.0 < avg_in_band <= MAX_COMPENSATION_DB

    def test_gain_capped_at_max(self):
        """Extreme loss should be capped at MAX_COMPENSATION_DB."""
        grid = self._grid()
        thresholds = {f: NORMAL_HEARING_REFERENCE[f] + 100.0 for f in TEST_FREQUENCIES}
        profile = _make_profile(thresholds)
        comp = compute_compensation_curve(profile, grid)
        assert np.all(comp <= MAX_COMPENSATION_DB + 0.01)  # small tolerance for smoothing

    def test_no_negative_gain(self):
        """Never apply negative EQ compensation (no cuts below reference)."""
        grid = self._grid()
        thresholds = {f: NORMAL_HEARING_REFERENCE[f] - 10.0 for f in TEST_FREQUENCIES}
        profile = _make_profile(thresholds)
        comp = compute_compensation_curve(profile, grid)
        assert np.all(comp >= 0.0)

    def test_returns_zeros_for_undetermined_profile(self):
        """If no frequencies are determined, return a zero array."""
        grid = self._grid()
        side = {
            f: FrequencyThreshold(freq_hz=f, level_dbfs=None, ascending_runs=0, determined=False)
            for f in TEST_FREQUENCIES
        }
        profile = HearingProfile(left=dict(side), right=dict(side), tested_at="2026-01-01T00:00:00+00:00", asymmetric_freqs=[])
        comp = compute_compensation_curve(profile, grid)
        assert np.all(comp == 0.0)

    def test_output_length_matches_grid(self):
        grid = self._grid()
        profile = _make_profile(NORMAL_HEARING_REFERENCE)
        comp = compute_compensation_curve(profile, grid)
        assert len(comp) == len(grid)

    def test_left_only_profile(self):
        """Profile with only left ear determined should still produce compensation."""
        grid = self._grid()
        thresholds = {f: NORMAL_HEARING_REFERENCE[f] + 20.0 for f in TEST_FREQUENCIES}
        left = {
            f: FrequencyThreshold(freq_hz=f, level_dbfs=t, ascending_runs=3, determined=True)
            for f, t in thresholds.items()
        }
        right = {
            f: FrequencyThreshold(freq_hz=f, level_dbfs=None, ascending_runs=0, determined=False)
            for f in TEST_FREQUENCIES
        }
        profile = HearingProfile(left=left, right=right, tested_at="2026-01-01T00:00:00+00:00", asymmetric_freqs=[])
        comp = compute_compensation_curve(profile, grid)
        assert np.max(comp) > 1.0


# ── detect_asymmetric_frequencies ────────────────────────────────────────────

class TestDetectAsymmetricFrequencies:
    def _t(self, freq_hz: int, level: float) -> FrequencyThreshold:
        return FrequencyThreshold(freq_hz=freq_hz, level_dbfs=level, ascending_runs=3, determined=True)

    def test_symmetric_gives_empty(self):
        left = {f: self._t(f, -40.0) for f in TEST_FREQUENCIES}
        right = {f: self._t(f, -40.0) for f in TEST_FREQUENCIES}
        assert detect_asymmetric_frequencies(left, right) == []

    def test_large_gap_detected(self):
        left = {f: self._t(f, -40.0) for f in TEST_FREQUENCIES}
        right = {f: self._t(f, -40.0) for f in TEST_FREQUENCIES}
        right[4000] = self._t(4000, -20.0)  # 20 dB gap
        result = detect_asymmetric_frequencies(left, right)
        assert 4000 in result

    def test_small_gap_not_flagged(self):
        left = {f: self._t(f, -40.0) for f in TEST_FREQUENCIES}
        right = {f: self._t(f, -40.0) for f in TEST_FREQUENCIES}
        right[1000] = self._t(1000, -33.0)  # 7 dB gap — below threshold
        result = detect_asymmetric_frequencies(left, right)
        assert 1000 not in result


# ── HearingProfile serialisation ──────────────────────────────────────────────

class TestHearingProfileSerialisation:
    def _sample_profile(self) -> HearingProfile:
        side = {
            f: FrequencyThreshold(freq_hz=f, level_dbfs=-40.0, ascending_runs=3, determined=True)
            for f in TEST_FREQUENCIES
        }
        return HearingProfile(
            left=dict(side),
            right=dict(side),
            tested_at="2026-01-01T00:00:00+00:00",
            asymmetric_freqs=[],
        )

    def test_round_trip(self):
        profile = self._sample_profile()
        data = profile.to_dict()
        restored = HearingProfile.from_dict(data)
        assert restored.tested_at == profile.tested_at
        assert restored.asymmetric_freqs == profile.asymmetric_freqs
        for freq_hz in TEST_FREQUENCIES:
            orig = profile.left[freq_hz]
            rest = restored.left[freq_hz]
            assert orig.freq_hz == rest.freq_hz
            assert orig.level_dbfs == pytest.approx(rest.level_dbfs)
            assert orig.determined == rest.determined

    def test_json_serialisable(self):
        profile = self._sample_profile()
        data = profile.to_dict()
        text = json.dumps(data)
        assert isinstance(text, str)
        assert "tested_at" in text

    def test_save_load(self, tmp_path, monkeypatch):
        monkeypatch.setattr("headmatch.hearing_test.config_dir", lambda: tmp_path)
        profile = self._sample_profile()
        path = save_hearing_profile(profile)
        assert path.exists()
        loaded = load_hearing_profile()
        assert loaded is not None
        assert loaded.tested_at == profile.tested_at

    def test_load_returns_none_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr("headmatch.hearing_test.config_dir", lambda: tmp_path)
        assert load_hearing_profile() is None

    def test_load_returns_none_on_corrupt_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("headmatch.hearing_test.config_dir", lambda: tmp_path)
        (tmp_path / "hearing_profile.json").write_text("not valid json", encoding="utf-8")
        assert load_hearing_profile() is None
