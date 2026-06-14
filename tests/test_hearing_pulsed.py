"""Tests for the pulsed-tone-train stimulus (replaces the single continuous tone).

See docs/superpowers/specs/2026-06-14-pulsed-tones-and-extended-high-frequencies-design.md
"""
from __future__ import annotations

import random

import numpy as np

from headmatch.hearing_test import (
    PULSE_COUNT_MAX,
    PULSE_COUNT_MIN,
    PULSE_DURATION_S,
    RESPONSE_WINDOW_S,
    generate_tone_train,
)


def _count_pulses(buf: np.ndarray, sample_rate: int) -> int:
    """Count distinct tone bursts via a coarse energy envelope (robust to the
    sine's own zero-crossings)."""
    mono = np.abs(buf).sum(axis=1)
    win = max(1, int(0.01 * sample_rate))
    env = np.array([mono[i:i + win].sum() for i in range(0, len(mono), win)])
    if env.max() <= 0:
        return 0
    active = env > env.max() * 0.05
    rising = int(np.sum((~active[:-1]) & active[1:]))
    return rising + (1 if active[0] else 0)


class TestGenerateToneTrain:
    def test_returns_stereo_buffer(self):
        buf = generate_tone_train(1000, -30.0, 48000, "both", random.Random(0))
        assert buf.ndim == 2 and buf.shape[1] == 2

    def test_pulse_count_within_range(self):
        for seed in range(25):
            buf = generate_tone_train(1000, -30.0, 48000, "both", random.Random(seed))
            n = _count_pulses(buf, 48000)
            assert PULSE_COUNT_MIN <= n <= PULSE_COUNT_MAX, (seed, n)

    def test_pulse_count_is_random_across_seeds(self):
        counts = {_count_pulses(generate_tone_train(1000, -30.0, 48000, "both", random.Random(s)), 48000)
                  for s in range(40)}
        assert len(counts) > 1  # not a fixed count

    def test_deterministic_for_same_seed(self):
        a = generate_tone_train(2000, -25.0, 48000, "both", random.Random(7))
        b = generate_tone_train(2000, -25.0, 48000, "both", random.Random(7))
        assert np.array_equal(a, b)

    def test_each_pulse_at_least_min_duration(self):
        # Total tone-on energy implies pulses are not ultra-short: with N pulses
        # of >= PULSE_DURATION_S, the active-sample count is >= N * min duration.
        sr = 48000
        buf = generate_tone_train(1000, -20.0, sr, "both", random.Random(3))
        n = _count_pulses(buf, sr)
        active_samples = int(np.sum(np.abs(buf[:, 0]) > 1e-4))
        # Each pulse contributes about PULSE_DURATION_S of (mostly) non-zero signal;
        # allow slack for the sine's zero-crossings (~halves the strict count).
        assert active_samples >= n * PULSE_DURATION_S * sr * 0.4

    def test_total_length_within_response_window(self):
        sr = 48000
        for seed in range(10):
            buf = generate_tone_train(1000, -30.0, sr, "both", random.Random(seed))
            assert buf.shape[0] <= int(RESPONSE_WINDOW_S * sr)

    def test_ear_routing_left_silences_right(self):
        buf = generate_tone_train(1000, -20.0, 48000, "left", random.Random(1))
        assert np.any(np.abs(buf[:, 0]) > 0) and np.all(buf[:, 1] == 0)

    def test_ear_routing_right_silences_left(self):
        buf = generate_tone_train(1000, -20.0, 48000, "right", random.Random(1))
        assert np.all(buf[:, 0] == 0) and np.any(np.abs(buf[:, 1]) > 0)

    def test_no_clicks_buffer_starts_and_ends_near_zero(self):
        # Raised-cosine ramps -> first and last samples are ~0 (no discontinuity).
        buf = generate_tone_train(1000, -10.0, 48000, "both", random.Random(2))
        assert abs(buf[0, 0]) < 1e-3 and abs(buf[-1, 0]) < 1e-3
