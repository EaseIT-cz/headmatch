from __future__ import annotations

import numpy as np

from headmatch.analysis import analyze_room_measurement
from headmatch.io_utils import write_wav
from headmatch.signals import SweepSpec, generate_log_sweep


def _make_room_recording(tmp_path, latency_samples=0, channels=1):
    spec = SweepSpec(sample_rate=48000, duration_s=1.0, f_start=20.0, f_end=20000.0,
                     pre_silence_s=0.1, post_silence_s=0.2, amplitude=0.3)
    stereo, mono = generate_log_sweep(spec)
    # Build a mono "mic" capture: silence + sweep + silence, optionally delayed.
    pre = np.zeros(int(spec.pre_silence_s * spec.sample_rate) + latency_samples)
    post = np.zeros(int(spec.post_silence_s * spec.sample_rate))
    cap = np.concatenate([pre, mono, post])
    if channels == 1:
        data = cap.reshape(-1, 1)
    else:
        data = np.column_stack([cap, cap])
    path = tmp_path / "room.wav"
    write_wav(path, data, spec.sample_rate)
    return path, spec


def test_accepts_mono_capture_and_returns_symmetric_result(tmp_path):
    path, spec = _make_room_recording(tmp_path, channels=1)
    result = analyze_room_measurement(path, spec)
    assert result.left_db.shape == result.freqs_hz.shape
    np.testing.assert_array_equal(result.left_db, result.right_db)
    np.testing.assert_array_equal(result.left_raw_db, result.right_raw_db)
    assert result.diagnostics["channel_mismatch_rms_db"] == 0.0
    # 1 kHz normalisation anchor: response at 1 kHz is ~0 dB
    one_k = float(np.interp(1000.0, result.freqs_hz, result.left_db))
    assert abs(one_k) < 0.5


def test_alignment_tolerates_large_round_trip_latency(tmp_path):
    # Simulated USB-mic latency of ~50 ms must not break alignment / clip the sweep.
    path_a, spec = _make_room_recording(tmp_path, latency_samples=0, channels=1)
    result_a = analyze_room_measurement(path_a, spec)
    path_b, _ = _make_room_recording(tmp_path, latency_samples=2400, channels=1)  # 50 ms @ 48k
    result_b = analyze_room_measurement(path_b, spec)
    # Same underlying sweep -> recovered FR should match within a small tolerance.
    rms_diff = float(np.sqrt(np.mean((result_a.left_db - result_b.left_db) ** 2)))
    assert rms_diff < 1.0


def test_accepts_stereo_capture_using_selected_channel(tmp_path):
    path, spec = _make_room_recording(tmp_path, channels=2)
    result = analyze_room_measurement(path, spec, mic_channel=0)
    assert result.left_db.shape == result.freqs_hz.shape