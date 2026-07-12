"""Coverage tests for headmatch.analysis — drives error branches and edge cases."""
from __future__ import annotations

import numpy as np
import pytest

from headmatch.analysis import (
    _alignment_reference_score,
    _align_recording_to_reference,
    _band_mask,
    _channel_mismatch_db,
    _coerce_measurement_audio,
    _roughness_db,
    analyze_measurement,
)
from headmatch.exceptions import MeasurementError
from headmatch.io_utils import write_wav
from headmatch.signals import SweepSpec, generate_log_sweep


class TestCoerceMeasurementAudio:
    def test_non_2d_raises(self):
        with pytest.raises(MeasurementError, match="must be a 2D audio array"):
            _coerce_measurement_audio(np.zeros(10), "x.wav")

    def test_empty_raises(self):
        with pytest.raises(MeasurementError, match="is empty"):
            _coerce_measurement_audio(np.zeros((0, 2)), "x.wav")

    def test_mono_capture_raises(self):
        with pytest.raises(MeasurementError, match="mono capture"):
            _coerce_measurement_audio(np.ones((10, 1)), "x.wav")

    def test_zero_channels_raises(self):
        # Rows present but zero columns: passes the empty/len check but trips
        # the "at least two channels" guard (shape[1] < 2, not == 1).
        with pytest.raises(MeasurementError, match="at least two channels"):
            _coerce_measurement_audio(np.zeros((10, 0)), "x.wav")

    def test_duplicated_channel_raises(self):
        mono = np.linspace(-1, 1, 32)
        stereo = np.column_stack([mono, mono])
        with pytest.raises(MeasurementError, match="duplicated-channel"):
            _coerce_measurement_audio(stereo, "x.wav")

    def test_valid_stereo_returns_two_channels(self):
        data = np.column_stack([
            np.linspace(-1, 1, 16),
            np.linspace(1, -1, 16),
            np.zeros(16),
        ])
        out = _coerce_measurement_audio(data, "x.wav")
        assert out.shape == (16, 2)


class TestAlignmentReferenceScore:
    def test_zero_denominator_returns_zero(self):
        # All-constant segment -> after mean removal it is all zeros -> denom 0
        seg = np.ones(10)
        ref = np.ones(10)
        assert _alignment_reference_score(seg, ref) == 0.0


class TestAlignHelpers:
    def _make_sweep(self, duration_s=0.3, sr=48000):
        t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
        return np.sin(2 * np.pi * (200 + 4000 * t) * t).astype(np.float64)

    def test_negative_offset_truncates_head(self):
        # Reference longer than recording forces a negative best offset path.
        sr = 48000
        sweep = self._make_sweep(0.3, sr)
        # Recording is the sweep but missing its first chunk: the true alignment
        # offset is negative, exercising lines 101-103 (truncated_head).
        cut = 2000
        rec_mono = sweep[cut:].copy()
        recording = np.column_stack([rec_mono, rec_mono * 0.9 + 1e-6])
        aligned, diag = _align_recording_to_reference(recording, sweep)
        assert diag["alignment_head_trimmed_samples"] >= 0.0
        assert aligned.shape[1] == 2

    def test_global_max_appended_when_not_a_peak(self):
        # A single-sample reference yields a length-1 correlation; find_peaks
        # returns no peaks (endpoints excluded), so the global max must be
        # appended explicitly (line 68).
        recording = np.array([[1.0, 0.5]])
        reference = np.array([1.0])
        aligned, diag = _align_recording_to_reference(recording, reference)
        assert aligned.shape == (1, 2)
        assert diag["alignment_offset_samples"] == 0.0

    def test_many_peaks_limited_to_top16(self):
        # Construct a recording with many repeated sweep copies so find_peaks
        # returns > 16 candidates, exercising lines 68/72-73.
        sr = 8000
        sweep = self._make_sweep(0.02, sr)
        gap = len(sweep)
        n_copies = 25
        total = n_copies * (len(sweep) + gap) + gap
        rec_mono = np.zeros(total)
        for i in range(n_copies):
            start = gap + i * (len(sweep) + gap)
            rec_mono[start:start + len(sweep)] += sweep
        recording = np.column_stack([rec_mono, rec_mono * 0.8 + 1e-9])
        aligned, diag = _align_recording_to_reference(recording, sweep)
        assert aligned.shape[1] == 2
        assert "alignment_offset_samples" in diag


class TestRoughnessAndMismatch:
    def test_roughness_empty_mask_returns_zero(self):
        mask = np.zeros(5, dtype=bool)
        assert _roughness_db(np.ones(5), np.zeros(5), mask) == 0.0

    def test_channel_mismatch_empty_mask_returns_zero(self):
        mask = np.zeros(5, dtype=bool)
        assert _channel_mismatch_db(np.ones(5), np.zeros(5), mask) == 0.0


def _write_valid_recording(path, spec):
    stereo, reference = generate_log_sweep(spec)
    padded_len = int(round(
        (spec.pre_silence_s + spec.duration_s + spec.post_silence_s) * spec.sample_rate
    ))
    rec = np.zeros((padded_len, 2))
    start = int(round(spec.pre_silence_s * spec.sample_rate))
    rec[start:start + len(reference), 0] = reference
    rec[start:start + len(reference), 1] = reference * 0.95 + 1e-6
    write_wav(path, rec, spec.sample_rate)


class TestAnalyzeMeasurement:
    def test_sample_rate_mismatch_raises(self, tmp_path):
        spec = SweepSpec(sample_rate=48000, duration_s=0.3,
                         pre_silence_s=0.1, post_silence_s=0.1)
        wav = tmp_path / "rec.wav"
        _write_valid_recording(wav, spec)
        # Analyze with a spec that claims a different sample rate.
        bad_spec = SweepSpec(sample_rate=44100, duration_s=0.3,
                             pre_silence_s=0.1, post_silence_s=0.1)
        with pytest.raises(MeasurementError, match="Sample rate mismatch"):
            analyze_measurement(wav, bad_spec)

    def test_recording_too_short_raises(self, tmp_path):
        spec = SweepSpec(sample_rate=48000, duration_s=0.3,
                         pre_silence_s=0.1, post_silence_s=0.1)
        # Write a too-short but valid stereo recording.
        short = np.column_stack([
            np.linspace(-1, 1, 100),
            np.linspace(1, -1, 100) * 0.9,
        ])
        wav = tmp_path / "short.wav"
        write_wav(wav, short, spec.sample_rate)
        with pytest.raises(MeasurementError, match="Recording too short"):
            analyze_measurement(wav, spec)

    def test_full_analysis_writes_csvs(self, tmp_path):
        spec = SweepSpec(sample_rate=48000, duration_s=0.3,
                         pre_silence_s=0.1, post_silence_s=0.1)
        wav = tmp_path / "rec.wav"
        _write_valid_recording(wav, spec)
        out_dir = tmp_path / "out"
        result = analyze_measurement(wav, spec, out_dir=out_dir)
        assert (out_dir / "measurement_left.csv").exists()
        assert (out_dir / "measurement_right.csv").exists()
        assert result.left_db.shape == result.freqs_hz.shape
