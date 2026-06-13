"""Integration tests: hearing compensation through the pipeline."""
from __future__ import annotations

import numpy as np
import pytest

from headmatch.hearing_test import (
    NORMAL_HEARING_REFERENCE,
    TEST_FREQUENCIES,
    FrequencyThreshold,
    HearingProfile,
    compute_compensation_curve,
)
from headmatch.pipeline import fit_from_measurement
from headmatch.signals import geometric_log_grid
from headmatch.targets import create_flat_target
from headmatch.analysis import MeasurementResult


def _flat_result(n: int = 512) -> MeasurementResult:
    freqs = geometric_log_grid(20.0, 20000.0, 48)[:n]
    flat = np.zeros(len(freqs))
    return MeasurementResult(
        freqs_hz=freqs,
        left_db=flat.copy(),
        right_db=flat.copy(),
        left_raw_db=flat.copy(),
        right_raw_db=flat.copy(),
        diagnostics={
            "alignment_reference_score": 1.0,
            "alignment_peak_ratio": 1.0,
            "channel_mismatch_rms_db": 0.0,
            "left_roughness_db": 0.0,
            "right_roughness_db": 0.0,
            "capture_rms_dbfs": -20.0,
        },
    )


def _make_profile(loss_db: float = 0.0) -> HearingProfile:
    side = {
        f: FrequencyThreshold(
            freq_hz=f,
            level_dbfs=NORMAL_HEARING_REFERENCE[f] + loss_db,
            ascending_runs=3,
            determined=True,
        )
        for f in TEST_FREQUENCIES
    }
    return HearingProfile(
        left=dict(side),
        right=dict(side),
        tested_at="2026-01-01T00:00:00+00:00",
        asymmetric_freqs=[],
    )


class TestHearingCompensationInPipeline:
    def test_no_compensation_without_profile(self):
        result = _flat_result()
        target = create_flat_target(result.freqs_hz)
        left_bands, right_bands, report = fit_from_measurement(
            result, target, sample_rate=48000, max_filters=4
        )
        assert report["hearing_compensation_applied"] is False

    def test_compensation_applied_flag_when_profile_present(self):
        result = _flat_result()
        target = create_flat_target(result.freqs_hz)
        profile = _make_profile(loss_db=0.0)
        _, _, report = fit_from_measurement(
            result, target, sample_rate=48000, max_filters=4,
            hearing_profile=profile,
        )
        assert report["hearing_compensation_applied"] is True

    def test_normal_hearing_produces_near_flat_target(self):
        """For a person at the normal hearing reference, compensation ≈ 0 dB → same EQ as without."""
        result = _flat_result()
        target = create_flat_target(result.freqs_hz)
        profile = _make_profile(loss_db=0.0)

        left_no_comp, _, _ = fit_from_measurement(result, target, sample_rate=48000, max_filters=4)
        left_with_comp, _, _ = fit_from_measurement(
            result, target, sample_rate=48000, max_filters=4,
            hearing_profile=profile,
        )
        # With 0 dB compensation, both fits should be very similar
        from headmatch.peq import peq_chain_response_db
        r_no = peq_chain_response_db(result.freqs_hz, 48000, left_no_comp)
        r_with = peq_chain_response_db(result.freqs_hz, 48000, left_with_comp)
        diff = np.abs(r_with - r_no)
        assert float(np.max(diff)) < 3.0  # within 3 dB

    def test_20dB_loss_shifts_eq_upward(self):
        """20 dB loss → half-gain = 10 dB compensation → EQ bands boosted."""
        result = _flat_result()
        target = create_flat_target(result.freqs_hz)
        profile = _make_profile(loss_db=20.0)

        left_no_comp, _, _ = fit_from_measurement(result, target, sample_rate=48000, max_filters=8)
        left_with_comp, _, _ = fit_from_measurement(
            result, target, sample_rate=48000, max_filters=8,
            hearing_profile=profile,
        )
        from headmatch.peq import peq_chain_response_db
        r_no = peq_chain_response_db(result.freqs_hz, 48000, left_no_comp)
        r_with = peq_chain_response_db(result.freqs_hz, 48000, left_with_comp)

        # The compensated version should have more total boost
        mask = (result.freqs_hz >= 500) & (result.freqs_hz <= 8000)
        boost_no = float(np.mean(r_no[mask]))
        boost_with = float(np.mean(r_with[mask]))
        assert boost_with > boost_no


class TestComputeCompensationCurveProperties:
    def test_monotonic_with_loss(self):
        """More loss → more compensation (checked at 1 kHz)."""
        grid = geometric_log_grid(20.0, 20000.0, 48)
        gains = []
        for loss in (0.0, 10.0, 20.0, 30.0):
            profile = _make_profile(loss_db=loss)
            comp = compute_compensation_curve(profile, grid)
            # Pick the grid point nearest 1 kHz
            idx = int(np.argmin(np.abs(grid - 1000.0)))
            gains.append(float(comp[idx]))
        assert gains[0] <= gains[1] <= gains[2] <= gains[3]

    def test_gain_fraction_relationship(self):
        """At exactly 20 dB loss, expected gain at 1 kHz ≈ 10 dB (before smoothing)."""
        from headmatch.hearing_test import GAIN_FRACTION
        grid = np.array([1000.0])
        profile = _make_profile(loss_db=20.0)
        comp = compute_compensation_curve(profile, grid)
        expected = 20.0 * GAIN_FRACTION
        # Within 2 dB due to interpolation and smoothing
        assert abs(float(comp[0]) - expected) < 2.0
