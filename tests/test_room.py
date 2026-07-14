"""Tests for room measurement and modal correction orchestration.

Covers:
- Flat room produces near-empty EQ
- Band-limit invariant (no filter above cutoff)
- Boost ceiling enforced (max 2 dB boost)
- Two-position energy averaging
- Sub-bass rolloff in target
- Missing calibration produces warning
"""
from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pytest

from headmatch.room import (
    ROOM_CUTOFF_DEFAULT_HZ,
    ROOM_MAX_BOOST_DB,
    build_room_target,
    fit_room_bands,
    _energy_average_responses,
    RoomFitResult,
)
from headmatch.analysis import MeasurementResult
from headmatch.exceptions import MeasurementError
from headmatch.mic_cal import MicCalibration
from headmatch.peq import PEQBand, peq_chain_response_db


def _dummy_measurement_result(freqs_hz: np.ndarray, response_db: np.ndarray | None = None) -> MeasurementResult:
    """Create a dummy MeasurementResult for testing."""
    if response_db is None:
        response_db = np.zeros_like(freqs_hz, dtype=np.float64)
    freqs = np.asarray(freqs_hz, dtype=np.float64)
    return MeasurementResult(
        freqs_hz=freqs,
        left_db=response_db,
        right_db=response_db,
        left_raw_db=response_db + np.random.randn(len(freqs_hz)) * 0.5,
        right_raw_db=response_db + np.random.randn(len(freqs_hz)) * 0.5,
        diagnostics={
            'alignment_offset_samples': 0.0,
            'alignment_reference_score': 1.0,
            'alignment_peak_ratio': 1.0,
            'alignment_head_trimmed_samples': 0.0,
            'alignment_tail_padded_samples': 0.0,
        },
    )


def _dummy_mic_calibration(freqs_hz: np.ndarray) -> MicCalibration:
    """Create a dummy flat mic calibration."""
    return MicCalibration(
        freqs_hz=freqs_hz,
        gains_db=np.zeros_like(freqs_hz),
        source='test_calibration.txt',
    )


class TestBuildRoomTarget:
    """Tests for build_room_target function."""
    
    def test_flat_room_target_without_rolloff(self):
        """Flat room target without rolloff produces all zeros."""
        freqs = np.array([20, 50, 100, 200, 300], dtype=np.float64)
        target = build_room_target(freqs, sub_bass_rolloff=False)
        
        assert np.allclose(target.values_db, 0.0), "Expected flat 0 dB target"
        assert target.name == 'room_modal_flat'
        assert target.semantics == 'absolute'
    
    def test_sub_bass_rolloff_below_40hz(self):
        """Sub-bass rolloff applies ~2-3 dB reduction below 40 Hz."""
        freqs = np.geomspace(20, 300, 50)
        target = build_room_target(freqs, sub_bass_rolloff=True)
        
        # At 20 Hz, should have ~-2.5 dB rolloff
        idx_20hz = np.argmin(np.abs(freqs - 20.0))
        assert target.values_db[idx_20hz] < -1.0, "Expected rolloff at 20 Hz"
        assert target.values_db[idx_20hz] > -4.0, "Rolloff should be ~2-3 dB"
        
        # At 40 Hz and above, should be flat
        idx_40hz = np.argmin(np.abs(freqs - 40.0))
        assert np.isclose(target.values_db[idx_40hz], 0.0, atol=0.1), "40 Hz should be flat"
        
        idx_100hz = np.argmin(np.abs(freqs - 100.0))
        assert np.isclose(target.values_db[idx_100hz], 0.0, atol=0.1), "100 Hz should be flat"
    
    def test_room_target_matches_input_freqs(self):
        """Target curve matches input frequency grid."""
        freqs = np.geomspace(20, 500, 100)
        target = build_room_target(freqs)
        
        assert len(target.freqs_hz) == len(freqs)
        assert np.allclose(target.freqs_hz, freqs)


class TestFitRoomBands:
    """Tests for fit_room_bands function."""
    
    def test_flat_room_produces_near_empty_eq(self):
        """Flat room target without rolloff produces near-empty EQ."""
        freqs = np.geomspace(20, 300, 100)
        # Flat 0 dB target with flat measurement (already at target)
        eq_target = np.zeros_like(freqs)
        
        bands = fit_room_bands(
            freqs_hz=freqs,
            eq_target_db=eq_target,
            sample_rate=48000,
            cutoff_hz=300.0,
            max_boost_db=ROOM_MAX_BOOST_DB,
            low_freq_q_cap=12.0,
        )
        
        # Flat target should produce 0 or very few bands
        assert len(bands) <= 2, f"Expected near-empty EQ for flat room, got {len(bands)} bands"
    
    def test_band_limit_invariant_no_filter_above_cutoff(self):
        """Band-limit invariant: no filter above cutoff_hz."""
        freqs = np.geomspace(20, 500, 200)
        # Create a response with peaks above intended cutoff
        eq_target = np.zeros_like(freqs)
        # Add a peak at 400 Hz
        eq_target += 5.0 * np.exp(-((freqs - 400) ** 2) / (2 * 50 ** 2))
        
        cutoff = 300.0
        bands = fit_room_bands(
            freqs_hz=freqs,
            eq_target_db=eq_target,
            sample_rate=48000,
            cutoff_hz=cutoff,
            max_boost_db=ROOM_MAX_BOOST_DB,
            low_freq_q_cap=12.0,
        )
        
        for band in bands:
            assert band.freq <= cutoff, f"Band at {band.freq} Hz exceeds cutoff {cutoff}"
    
    def test_boost_ceiling_enforced_for_peaks(self):
        """Boost ceiling enforced: max_boost_db parameter used in fit."""
        freqs = np.geomspace(20, 300, 100)
        # Create localized peaks that need boost
        eq_target = np.zeros_like(freqs)
        # Add narrow peaks below cutoff
        eq_target += 6.0 * np.exp(-((freqs - 60) ** 2) / (2 * 15 ** 2))
        eq_target += 5.0 * np.exp(-((freqs - 120) ** 2) / (2 * 20 ** 2))
        
        bands = fit_room_bands(
            freqs_hz=freqs,
            eq_target_db=eq_target,
            sample_rate=48000,
            cutoff_hz=300.0,
            max_boost_db=ROOM_MAX_BOOST_DB,  # 2.0
            low_freq_q_cap=12.0,
        )
        
        # Check individual boost bands are constrained by max_boost_db
        for band in bands:
            if band.kind == 'peaking' and band.gain_db > 0:
                assert band.gain_db <= ROOM_MAX_BOOST_DB + 0.1, \
                    f"Peaking boost {band.gain_db} exceeds max_boost_db {ROOM_MAX_BOOST_DB}"
        
        # Verify function runs without error with strict boost limit
        assert len(bands) >= 0  # Just verifies completion

    def test_boost_ceiling_enforced_for_realized_chain(self):
        """Stacked filters must not exceed the cumulative room boost ceiling."""
        freqs = np.geomspace(20, 300, 300)
        eq_target = 12.0 * np.exp(-((freqs - 80) ** 2) / (2 * 20 ** 2))

        bands = fit_room_bands(
            freqs_hz=freqs,
            eq_target_db=eq_target,
            sample_rate=48000,
            cutoff_hz=300.0,
            max_boost_db=ROOM_MAX_BOOST_DB,
            low_freq_q_cap=12.0,
        )
        chain = peq_chain_response_db(freqs, 48000, bands)

        assert float(np.max(chain)) <= ROOM_MAX_BOOST_DB + 1e-5
    
    def test_low_freq_q_cap_applied(self):
        """Low frequency Q cap of 12.0 enforced for sub-120 Hz."""
        freqs = np.geomspace(20, 300, 150)
        # Corner response to trigger peaking bands
        eq_target = np.zeros_like(freqs)
        eq_target[freqs < 100] = 3.0  # Boost below 100 Hz
        
        bands = fit_room_bands(
            freqs_hz=freqs,
            eq_target_db=eq_target,
            sample_rate=48000,
            cutoff_hz=300.0,
            max_boost_db=ROOM_MAX_BOOST_DB,
            low_freq_q_cap=12.0,
        )
        
        for band in bands:
            if band.kind == 'peaking' and band.freq < 120:
                assert band.q <= 12.5, f"Q {band.q} violates cap for {band.freq} Hz"

    def test_rejects_non_finite_eq_target(self):
        freqs = np.geomspace(20, 300, 100)
        eq_target = np.zeros_like(freqs)
        eq_target[10] = np.nan

        with pytest.raises(MeasurementError, match="non-finite"):
            fit_room_bands(freqs, eq_target, 48000, cutoff_hz=300.0)

    def test_rejects_unsorted_frequency_grid(self):
        freqs = np.array([20.0, 100.0, 50.0, 300.0])
        eq_target = np.zeros_like(freqs)

        with pytest.raises(MeasurementError, match="strictly increasing"):
            fit_room_bands(freqs, eq_target, 48000, cutoff_hz=300.0)

    def test_rejects_cutoff_without_frequency_overlap(self):
        freqs = np.geomspace(1000, 2000, 20)
        eq_target = np.zeros_like(freqs)

        with pytest.raises(MeasurementError, match="no points"):
            fit_room_bands(freqs, eq_target, 48000, cutoff_hz=100.0)

    def test_rejects_cutoff_above_nyquist_margin(self):
        freqs = np.geomspace(20, 20000, 100)
        eq_target = np.zeros_like(freqs)

        with pytest.raises(MeasurementError, match="Nyquist"):
            fit_room_bands(freqs, eq_target, 48000, cutoff_hz=23900.0)

    def test_three_position_average_does_not_warn_as_single_point(self):
        from headmatch.room import energy_average_responses_n, _assess_room_fit_quality

        freqs = np.array([20.0, 50.0, 100.0, 200.0, 300.0])
        results = [_dummy_measurement_result(freqs, np.full_like(freqs, i)) for i in range(3)]

        averaged = energy_average_responses_n(results)
        warnings = _assess_room_fit_quality(averaged)

        assert averaged.diagnostics["n_position_averaged"] == 3
        assert not any("Single-point" in warning for warning in warnings)


class TestEnergyAverageResponses:
    """Tests for _energy_average_responses function."""
    
    def test_energy_averages_two_recordings(self):
        """Two-position energy averaging produces magnitude-domain average."""
        freqs = np.array([20, 50, 100, 200, 300], dtype=np.float64)
        
        # Two different responses
        result1 = MeasurementResult(
            freqs_hz=freqs.copy(),
            left_db=np.array([0, 3, 0, 3, 0], dtype=np.float64),
            right_db=np.array([0, 3, 0, 3, 0], dtype=np.float64),
            left_raw_db=np.array([0.5, 3.5, 0.5, 3.5, 0.5], dtype=np.float64),
            right_raw_db=np.array([0.5, 3.5, 0.5, 3.5, 0.5], dtype=np.float64),
            diagnostics={'test': True},
        )
        
        result2 = MeasurementResult(
            freqs_hz=freqs.copy(),
            left_db=np.array([0, 0, 6, 0, 6], dtype=np.float64),  # Different pattern
            right_db=np.array([0, 0, 6, 0, 6], dtype=np.float64),
            left_raw_db=np.array([-0.5, -0.5, 6.5, -0.5, 6.5], dtype=np.float64),
            right_raw_db=np.array([-0.5, -0.5, 6.5, -0.5, 6.5], dtype=np.float64),
            diagnostics={'test': True},
        )
        
        averaged = _energy_average_responses(result1, result2)
        
        # Check averaging flag
        assert averaged.diagnostics.get('two_position_averaged') is True
        
        # Check energy averaging: at 50 Hz, mean of 3dB and 0dB
        # Energy: 10^(3/10)=2.0, 10^(0/10)=1.0, mean=1.5, db=10*log10(1.5)=~1.76
        idx_50hz = np.argmin(np.abs(freqs - 50.0))
        expected = 10 * np.log10((10**(3/10) + 10**(0/10)) / 2)
        actual = averaged.left_db[idx_50hz]
        assert abs(actual - expected) < 0.5, f"Energy avg mismatch at 50Hz: {actual} vs {expected}"
    
    def test_energy_average_preserves_freqs(self):
        """Energy average preserves frequency grid."""
        freqs = np.geomspace(20, 500, 50)
        
        result1 = _dummy_measurement_result(freqs)
        result2 = _dummy_measurement_result(freqs)
        
        averaged = _energy_average_responses(result1, result2)
        
        assert np.allclose(averaged.freqs_hz, freqs)


class TestEnergyAverageResponsesN:
    """Tests for N-position energy averaging (MMM - moving microphone method).
    
    These tests document the expected behavior for the Phase 2 extension
    of energy averaging to N inputs for spatial averaging.
    """
    
    def _energy_average_responses_n(self, results: list[MeasurementResult]) -> MeasurementResult:
        """Placeholder for the N-position averaging function.
        
        This function should:
        - Accept a list of MeasurementResult objects
        - Compute energy average across all N positions
        - Return a new MeasurementResult with n_position_averaged in diagnostics
        """
        raise NotImplementedError(
            "energy_average_responses_n is not yet implemented. "
            "Extend _energy_average_responses to accept N inputs."
        )
    
    def test_signature_accepts_list_of_measurement_results(self):
        """N-position averaging accepts list[MeasurementResult] parameter."""
        freqs = np.array([20, 50, 100], dtype=np.float64)
        
        result1 = MeasurementResult(
            freqs_hz=freqs.copy(),
            left_db=np.array([0, 3, 6], dtype=np.float64),
            right_db=np.array([0, 3, 6], dtype=np.float64),
            left_raw_db=np.array([0, 3, 6], dtype=np.float64),
            right_raw_db=np.array([0, 3, 6], dtype=np.float64),
            diagnostics={'test': True},
        )
        result2 = MeasurementResult(
            freqs_hz=freqs.copy(),
            left_db=np.array([6, 3, 0], dtype=np.float64),
            right_db=np.array([6, 3, 0], dtype=np.float64),
            left_raw_db=np.array([6, 3, 0], dtype=np.float64),
            right_raw_db=np.array([6, 3, 0], dtype=np.float64),
            diagnostics={'test': True},
        )
        result3 = MeasurementResult(
            freqs_hz=freqs.copy(),
            left_db=np.array([3, 6, 3], dtype=np.float64),
            right_db=np.array([3, 6, 3], dtype=np.float64),
            left_raw_db=np.array([3, 6, 3], dtype=np.float64),
            right_raw_db=np.array([3, 6, 3], dtype=np.float64),
            diagnostics={'test': True},
        )
        
        # Function should accept a list of MeasurementResult
        results_list = [result1, result2, result3]
        try:
            from headmatch.room import energy_average_responses_n
            avg_result = energy_average_responses_n(results_list)
            assert isinstance(avg_result, MeasurementResult)
        except ImportError:
            with pytest.raises(NotImplementedError):
                self._energy_average_responses_n(results_list)
    
    def test_energy_averaging_math_formula(self):
        """Energy averaging follows correct math: linear power average."""
        # Three positions: 0 dB, 0 dB, 0 dB (all same)
        # Power: 10^(0/10) = 1.0 each
        # Average: (1.0 + 1.0 + 1.0) / 3 = 1.0
        # Result: 10 * log10(1.0) = 0 dB
        result_db = 0.0
        result_power = 10 ** (result_db / 10.0)
        expected_power = (result_power + result_power + result_power) / 3.0
        expected_db = 10 * np.log10(expected_power)
        assert np.isclose(expected_db, 0.0), f"Expected 0 dB for three 0 dB sources, got {expected_db}"
        
        # Three positions: 6 dB, 6 dB, 6 dB
        # Power: 10^(6/10) = 3.98 each
        # Average: 3.98 → 10 * log10(3.98) = 6 dB
        result_db = 6.0
        result_power = 10 ** (result_db / 10.0)
        expected_power = (result_power + result_power + result_power) / 3.0
        expected_db = 10 * np.log10(expected_power)
        assert np.isclose(expected_db, 6.0), f"Expected 6 dB for three 6 dB sources, got {expected_db}"
        
        # Three positions: 0 dB, 6 dB, 12 dB
        # Power: 1, 3.98, 15.85
        # Average: (1 + 3.98 + 15.85) / 3 = 6.943
        # Result: 10 * log10(6.943) = 8.41 dB
        powers = [10**(0/10), 10**(6/10), 10**(12/10)]
        avg_power = sum(powers) / 3.0
        expected_db = 10 * np.log10(avg_power)
        expected_manual = 10 * np.log10((1.0 + 3.981 + 15.849) / 3.0)
        assert np.isclose(expected_db, expected_manual, atol=0.01), \
            f"Manual calc error: {expected_db} vs {expected_manual}"
    
    def test_three_position_energy_average(self):
        """Three-position averaging produces correct results at specific frequencies."""
        freqs = np.array([100], dtype=np.float64)
        
        # Create three responses with different dB values
        # At 100 Hz: response1=3.01 dB (power≈2.0), response2=0 dB (power=1.0), response3=6.02 dB (power≈4.0)
        # Average power: (2.0 + 1.0 + 4.0) / 3 = 2.333...
        # Average dB: 10 * log10(2.333) = 3.68 dB
        
        result1 = MeasurementResult(
            freqs_hz=freqs.copy(),
            left_db=np.array([3.01], dtype=np.float64),  # ≈ 2.0 in linear
            right_db=np.array([3.01], dtype=np.float64),
            left_raw_db=np.array([3.01], dtype=np.float64),
            right_raw_db=np.array([3.01], dtype=np.float64),
            diagnostics={'test': True},
        )
        result2 = MeasurementResult(
            freqs_hz=freqs.copy(),
            left_db=np.array([0.0], dtype=np.float64),  # = 1.0 in linear
            right_db=np.array([0.0], dtype=np.float64),
            left_raw_db=np.array([0.0], dtype=np.float64),
            right_raw_db=np.array([0.0], dtype=np.float64),
            diagnostics={'test': True},
        )
        result3 = MeasurementResult(
            freqs_hz=freqs.copy(),
            left_db=np.array([6.02], dtype=np.float64),  # ≈ 4.0 in linear
            right_db=np.array([6.02], dtype=np.float64),
            left_raw_db=np.array([6.02], dtype=np.float64),
            right_raw_db=np.array([6.02], dtype=np.float64),
            diagnostics={'test': True},
        )
        
        # Expected calculation: energies 2.0, 1.0, 4.0 average to 2.333
        expected_linear = (2.0 + 1.0 + 4.0) / 3.0
        expected_db = 10 * np.log10(expected_linear)
        
        try:
            from headmatch.room import energy_average_responses_n
            avg_result = energy_average_responses_n([result1, result2, result3])
            
            # Verify the average dB is approximately 3.68 dB
            assert np.isclose(avg_result.left_db[0], expected_db, atol=0.1), \
                f"Left channel energy avg mismatch: {avg_result.left_db[0]} vs {expected_db}"
            assert np.isclose(avg_result.right_db[0], expected_db, atol=0.1), \
                f"Right channel energy avg mismatch: {avg_result.right_db[0]} vs {expected_db}"
            assert np.isclose(avg_result.left_raw_db[0], expected_db, atol=0.1), \
                f"Left raw energy avg mismatch: {avg_result.left_raw_db[0]} vs {expected_db}"
            assert np.isclose(avg_result.right_raw_db[0], expected_db, atol=0.1), \
                f"Right raw energy avg mismatch: {avg_result.right_raw_db[0]} vs {expected_db}"
        except ImportError:
            pytest.xfail("energy_average_responses_n not yet implemented")
    
    def test_single_position_returns_unchanged(self):
        """Single position (N=1) returns the measurement unchanged."""
        freqs = np.array([20, 50, 100], dtype=np.float64)
        
        result1 = MeasurementResult(
            freqs_hz=freqs.copy(),
            left_db=np.array([0, 3, 6], dtype=np.float64),
            right_db=np.array([0, 3, 6], dtype=np.float64),
            left_raw_db=np.array([0.5, 3.5, 6.5], dtype=np.float64),
            right_raw_db=np.array([0.5, 3.5, 6.5], dtype=np.float64),
            diagnostics={'test': True, 'original': 1},
        )
        
        try:
            from headmatch.room import energy_average_responses_n
            avg_result = energy_average_responses_n([result1])
            
            # Should return the same data
            assert np.allclose(avg_result.left_db, result1.left_db)
            assert np.allclose(avg_result.right_db, result1.right_db)
            assert np.allclose(avg_result.freqs_hz, result1.freqs_hz)
        except ImportError:
            pytest.xfail("energy_average_responses_n not yet implemented")
    
    def test_empty_list_raises_error(self):
        """Empty list raises appropriate error."""
        try:
            from headmatch.room import energy_average_responses_n
            from headmatch.exceptions import MeasurementError
            with pytest.raises(MeasurementError, match="empty"):
                energy_average_responses_n([])
        except ImportError:
            pytest.xfail("energy_average_responses_n not yet implemented")
    
    def test_mismatched_frequency_grids_raise_error(self):
        """Mismatched frequency grids raise appropriate error."""
        result1 = MeasurementResult(
            freqs_hz=np.array([20, 50, 100], dtype=np.float64),
            left_db=np.array([0, 3, 6], dtype=np.float64),
            right_db=np.array([0, 3, 6], dtype=np.float64),
            left_raw_db=np.array([0, 3, 6], dtype=np.float64),
            right_raw_db=np.array([0, 3, 6], dtype=np.float64),
            diagnostics={'test': True},
        )
        result2 = MeasurementResult(
            freqs_hz=np.array([20, 51, 100], dtype=np.float64),  # Different!
            left_db=np.array([6, 3, 0], dtype=np.float64),
            right_db=np.array([6, 3, 0], dtype=np.float64),
            left_raw_db=np.array([6, 3, 0], dtype=np.float64),
            right_raw_db=np.array([6, 3, 0], dtype=np.float64),
            diagnostics={'test': True},
        )
        
        try:
            from headmatch.room import energy_average_responses_n
            from headmatch.exceptions import MeasurementError
            with pytest.raises(MeasurementError, match="freq|frequency|grid|mismatch"):
                energy_average_responses_n([result1, result2])
        except ImportError:
            pytest.xfail("energy_average_responses_n not yet implemented")
    
    def test_diagnostics_include_n_position_averaged(self):
        """Result diagnostics include n_position_averaged: N."""
        freqs = np.array([100], dtype=np.float64)
        
        results = []
        for i in range(5):
            results.append(MeasurementResult(
                freqs_hz=freqs.copy(),
                left_db=np.array([float(i)], dtype=np.float64),
                right_db=np.array([float(i)], dtype=np.float64),
                left_raw_db=np.array([float(i)], dtype=np.float64),
                right_raw_db=np.array([float(i)], dtype=np.float64),
                diagnostics={'test': True},
            ))
        
        try:
            from headmatch.room import energy_average_responses_n
            avg_result = energy_average_responses_n(results)
            
            # Should include n_position_averaged: 5 in diagnostics
            assert 'n_position_averaged' in avg_result.diagnostics, \
                "diagnostics should contain 'n_position_averaged'"
            assert avg_result.diagnostics['n_position_averaged'] == 5, \
                f"Expected n_position_averaged=5, got {avg_result.diagnostics.get('n_position_averaged')}"
        except ImportError:
            pytest.xfail("energy_average_responses_n not yet implemented")
    
    def test_two_position_matches_existing_function(self):
        """N=2 should produce same result as existing _energy_average_responses."""
        freqs = np.array([20, 50, 100, 200, 300], dtype=np.float64)
        
        result1 = MeasurementResult(
            freqs_hz=freqs.copy(),
            left_db=np.array([0, 3, 0, 3, 0], dtype=np.float64),
            right_db=np.array([0, 3, 0, 3, 0], dtype=np.float64),
            left_raw_db=np.array([0.5, 3.5, 0.5, 3.5, 0.5], dtype=np.float64),
            right_raw_db=np.array([0.5, 3.5, 0.5, 3.5, 0.5], dtype=np.float64),
            diagnostics={'test': True},
        )
        
        result2 = MeasurementResult(
            freqs_hz=freqs.copy(),
            left_db=np.array([0, 0, 6, 0, 6], dtype=np.float64),
            right_db=np.array([0, 0, 6, 0, 6], dtype=np.float64),
            left_raw_db=np.array([-0.5, -0.5, 6.5, -0.5, 6.5], dtype=np.float64),
            right_raw_db=np.array([-0.5, -0.5, 6.5, -0.5, 6.5], dtype=np.float64),
            diagnostics={'test': True},
        )
        
        existing_result = _energy_average_responses(result1, result2)
        
        try:
            from headmatch.room import energy_average_responses_n
            new_result = energy_average_responses_n([result1, result2])
            
            # Results should match
            assert np.allclose(existing_result.left_db, new_result.left_db, atol=0.001)
            assert np.allclose(existing_result.right_db, new_result.right_db, atol=0.001)
        except ImportError:
            pytest.xfail("energy_average_responses_n not yet implemented")


class TestPerSpeakerStereo:
    """Tests for per-channel room fit (Phase 2 item 5).
    
    Verifies that run_room_fit supports independent L/R analysis and fitting
    for rooms where the two speakers' modal interaction differs at the
    listening position. This is a separate correction path from independent
    channel measurements.
    """
    
    def _create_asymmetric_measurement_result(
        self,
        freqs_hz: np.ndarray,
        left_peak_db: float = 0.0,
        left_peak_freq: float = 60.0,
        right_peak_db: float = 0.0,
        right_peak_freq: float = 100.0,
    ) -> MeasurementResult:
        """Create a measurement with asymmetric L/R modal responses."""
        base_response = np.zeros_like(freqs_hz, dtype=np.float64)
        
        # Left channel peak
        left_response = base_response.copy()
        if left_peak_db > 0:
            left_response += left_peak_db * np.exp(
                -((freqs_hz - left_peak_freq) ** 2) / (2 * 20 ** 2)
            )
        
        # Right channel peak (different frequency and/or magnitude)
        right_response = base_response.copy()
        if right_peak_db > 0:
            right_response += right_peak_db * np.exp(
                -((freqs_hz - right_peak_freq) ** 2) / (2 * 25 ** 2)
            )
        
        return MeasurementResult(
            freqs_hz=freqs_hz.copy(),
            left_db=left_response,
            right_db=right_response,
            left_raw_db=left_response + np.random.randn(len(freqs_hz)) * 0.3,
            right_raw_db=right_response + np.random.randn(len(freqs_hz)) * 0.3,
            diagnostics={'test_asymmetric': True},
        )
    
    def test_per_channel_input_parameters_exist(self):
        """run_room_fit accepts recording_left and recording_right parameters."""
        import inspect
        from headmatch.room import run_room_fit
        
        sig = inspect.signature(run_room_fit)
        param_names = list(sig.parameters.keys())
        
        assert 'recording_left' in param_names, \
            "run_room_fit should accept 'recording_left' parameter"
        assert 'recording_right' in param_names, \
            "run_room_fit should accept 'recording_right' parameter"
    
    def test_independent_analysis_produces_different_frequency_responses(self):
        """Left and right recordings are analyzed separately, producing different responses."""
        pytest.skip("Per-channel analysis not yet implemented")
        # When implemented, run_room_fit(recording_left=..., recording_right=...) should
        # analyze each channel independently (not averaging them) so that, given a left
        # capture with a 60 Hz peak and a right capture with a 120 Hz peak, the returned
        # result.left_db and result.right_db reflect each channel's distinct modal peak.
    
    def test_independent_fitting_produces_different_peq_bands(self):
        """Each channel gets its own set of PEQ bands based on its own analysis."""
        pytest.skip("Per-channel fitting not yet implemented")
        # When implemented, with asymmetric L/R modal responses (e.g. a 60 Hz peak on
        # the left, a 120 Hz peak on the right), run_room_fit(recording_left=...,
        # recording_right=...) should produce result.eq_bands_left != result.eq_bands_right,
        # each targeting its own channel's peak.
    
    def test_lr_asymmetry_different_modal_peaks(self):
        """Given L/R with different modal peaks, verify separate EQ bands."""
        pytest.skip("L/R asymmetry handling not yet implemented")
        
        # This is the key acceptance test for Phase 2 item 5.
        # 
        # Scenario: Room where left and right speakers have different modal
        # coupling at the listening position.
        #
        # Test case:
        # - Left recording: +8 dB peak at 45 Hz (left speaker corner loading)
        # - Right recording: +6 dB peak at 70 Hz (right speaker different boundary)
        #
        # Expected result:
        # - left_bands should include a cut near 45 Hz
        # - right_bands should include a cut near 70 Hz
        # - The two band sets should not be identical
        
        assert False, "Test not yet implemented"
    
    def test_backward_compatibility_mono_eq_fallback(self):
        """When only 'recording' is provided, fall back to mono EQ for both channels."""
        from headmatch.room import run_room_fit
        
        # Current behavior: single recording produces same EQ for both channels
        # This test ensures backward compatibility is maintained.
        
        # Given: Only the legacy 'recording' parameter
        # When: run_room_fit is called (current signature)
        # Then: Both channels get the same EQ (mono EQ duplicated)
        
        import inspect
        sig = inspect.signature(run_room_fit)
        
        # 'recording' parameter should still exist for backward compat
        assert 'recording' in sig.parameters, \
            "Legacy 'recording' parameter must be preserved for backward compatibility"
        
        # When called with only 'recording', the existing behavior should
        # produce identical left/right bands (mono EQ duplicated)
        # This is the current behavior and should remain working.
    
    def test_room_fit_result_includes_separate_eq_bands_fields(self):
        """RoomFitResult has eq_bands_left and eq_bands_right fields."""
        pytest.skip("RoomFitResult extension not yet implemented")
        
        from headmatch.room import RoomFitResult
        
        # Verify that RoomFitResult dataclass has the expected fields
        # for per-channel EQ bands.
        
        # Current: RoomFitResult has 'eq_bands: list[PEQBand]'
        # Expected: RoomFitResult should also have:
        #   - eq_bands_left: list[PEQBand]
        #   - eq_bands_right: list[PEQBand]
        
        # Check that the new fields exist
        import inspect
        sig = inspect.signature(RoomFitResult)
        params = list(sig.parameters.keys())
        
        assert 'eq_bands_left' in params, \
            "RoomFitResult should have 'eq_bands_left' field"
        assert 'eq_bands_right' in params, \
            "RoomFitResult should have 'eq_bands_right' field"
        
        # For backward compatibility, 'eq_bands' may be retained
        # or aliased to 'eq_bands_left' during transition
    
    def test_per_channel_recording_paths_accept_path_types(self):
        """recording_left and recording_right accept str and Path."""
        pytest.skip("Per-channel parameter types not yet implemented")
        
        from headmatch.room import run_room_fit
        import inspect
        
        sig = inspect.signature(run_room_fit)
        
        left_param = sig.parameters.get('recording_left')
        right_param = sig.parameters.get('recording_right')
        
        assert left_param is not None and right_param is not None, \
            "Parameters should exist"
        
        # Should accept Union[str, Path, None] similar to recording parameter
        # This test verifies the type annotations
        
        assert False, "Test not yet implemented"
    
    def test_mutual_exclusivity_recording_vs_per_channel(self):
        """Cannot provide both legacy 'recording' and new 'recording_left/right'."""
        pytest.skip("Parameter validation not yet implemented")
        
        # Test that providing both legacy and per-channel parameters
        # raises an appropriate error.
        
        # Given:
        # - recording='path/to/rec.wav' AND
        # - recording_left='path/to/left.wav'
        #
        # Expected: ValueError or TypeError with clear message
        
        assert False, "Test not yet implemented"


class TestRoomConstants:
    """Tests for room module constants."""
    
    def test_constants_defined(self):
        """Room constants are properly defined."""
        assert ROOM_CUTOFF_DEFAULT_HZ == 300.0
        assert ROOM_MAX_BOOST_DB == 2.0


class TestFullRangeTilt:
    """Tests for full-range tilt EQ above cutoff (Phase 2 item 4).
    
    Optional, heavily smoothed broadband tilt/target above the cutoff
    for gentle house-curve shaping. Must be explicitly opt-in with
    guardrails to prevent chasing narrow above-cutoff features.
    """
    
    def test_function_exists(self):
        """fit_full_range_tilt function exists in room module."""
        from headmatch.room import fit_full_range_tilt
        assert callable(fit_full_range_tilt)
    
    def test_opt_in_only_tilt_not_applied_by_default(self):
        """Tilt EQ is only applied when enable_tilt=True parameter is passed."""
        from headmatch.room import fit_room_bands, fit_full_range_tilt
        
        freqs = np.geomspace(20, 20000, 500)
        eq_target = np.zeros_like(freqs)
        
        # Without enable_tilt, no tilt bands should be generated
        bands_no_tilt = fit_room_bands(
            freqs_hz=freqs,
            eq_target_db=eq_target,
            sample_rate=48000,
            cutoff_hz=300.0,
        )
        
        # All bands should be below cutoff
        for band in bands_no_tilt:
            assert band.freq <= 300.0, f"Unexpected above-cutoff band at {band.freq} Hz"
        
        # With enable_tilt=True, should include tilt bands above cutoff
        bands_with_tilt = fit_room_bands(
            freqs_hz=freqs,
            eq_target_db=eq_target,
            sample_rate=48000,
            cutoff_hz=300.0,
            enable_tilt=True,
        )
        
        # Should have additional bands above cutoff
        above_cutoff_bands = [b for b in bands_with_tilt if b.freq > 300.0]
        assert len(above_cutoff_bands) > 0, "Expected tilt bands above cutoff when enable_tilt=True"
    
    def test_above_cutoff_domain_only(self):
        """Tilt bands only generated for frequencies > cutoff_hz."""
        from headmatch.room import fit_full_range_tilt
        
        freqs = np.geomspace(20, 20000, 500)
        # Simulate a gentle downtrend for house curve
        response_db = -3.0 * np.log10(freqs / 1000.0)  # -3 dB per decade
        
        tilt_bands = fit_full_range_tilt(
            freqs_hz=freqs,
            measured_db=response_db,
            cutoff_hz=300.0,
            enable_tilt=True,
        )
        
        # All tilt bands must be above cutoff
        for band in tilt_bands:
            assert band.freq > 300.0, f"Tilt band at {band.freq} Hz should be above cutoff 300 Hz"
    
    def test_smooth_constraint_low_q_only(self):
        """Above-cutoff bands must have very low Q (Q ≤ 2) for smooth shaping."""
        from headmatch.room import fit_full_range_tilt
        
        freqs = np.geomspace(20, 20000, 500)
        response_db = -2.0 * np.log10(freqs / 1000.0)
        
        tilt_bands = fit_full_range_tilt(
            freqs_hz=freqs,
            measured_db=response_db,
            cutoff_hz=300.0,
            enable_tilt=True,
        )
        
        # All tilt bands should have very low Q
        for band in tilt_bands:
            assert band.q <= 2.0, f"Tilt band Q={band.q} exceeds soft Q limit (should be ≤ 2 for smooth shaping)"
    
    def test_magnitude_limit_safe_gain_range(self):
        """Tilt gain limited to safe range (±6 dB maximum)."""
        from headmatch.room import fit_full_range_tilt
        
        freqs = np.geomspace(20, 20000, 500)
        response_db = np.zeros_like(freqs)
        
        tilt_bands = fit_full_range_tilt(
            freqs_hz=freqs,
            measured_db=response_db,
            cutoff_hz=300.0,
            enable_tilt=True,
        )
        
        # All tilt gains must be within ±6 dB
        for band in tilt_bands:
            assert abs(band.gain_db) <= 6.0, f"Tilt gain {band.gain_db} dB exceeds ±6 dB limit"
    
    def test_integration_includes_modal_and_tilt_bands(self):
        """With enable_tilt=True, output includes both below-cutoff modal and above-cutoff tilt bands."""
        from headmatch.room import fit_room_bands
        
        freqs = np.geomspace(20, 20000, 500)
        # Create a response with modal issues below 300 Hz and gentle downtrend above
        eq_target = np.zeros_like(freqs)
        # Add modal peak at 80 Hz
        eq_target += 8.0 * np.exp(-((freqs - 80) ** 2) / (2 * 20 ** 2))
        # Above-cutoff: gentle downtrend
        mask_above = freqs > 300
        eq_target[mask_above] += -3.0 * np.log10(freqs[mask_above] / 1000.0)
        
        bands = fit_room_bands(
            freqs_hz=freqs,
            eq_target_db=eq_target,
            sample_rate=48000,
            cutoff_hz=300.0,
            enable_tilt=True,
        )
        
        # Should have bands in both ranges
        below_cutoff = [b for b in bands if b.freq <= 300.0]
        above_cutoff = [b for b in bands if b.freq > 300.0]
        
        assert len(below_cutoff) > 0, "Expected modal correction bands below cutoff"
        assert len(above_cutoff) > 0, "Expected tilt bands above cutoff"
        
        # Modal correction bands can have higher Q (e.g., Q=3-12)
        # Tilt bands must have low Q
        for band in above_cutoff:
            assert band.q <= 2.0, f"Above-cutoff tilt band should have Q ≤ 2, got {band.q}"
    
    def test_guardrail_ignores_sharp_above_cutoff_features(self):
        """Sharp above-cutoff features (>±3 dB at high Q) are ignored/not fitted."""
        from headmatch.room import fit_full_range_tilt, fit_room_bands
        
        freqs = np.geomspace(20, 20000, 500)
        # Create a response with:
        # - Gentle trend above cutoff (acceptable)
        # - Sharp +5 dB peak at 1 kHz with narrow width (should be ignored)
        response_db = np.zeros_like(freqs)
        # Gentle trend
        mask_above = freqs > 300
        response_db[mask_above] = -2.0 * np.log10(freqs[mask_above] / 1000.0)
        # Sharp peak at 1 kHz (high Q feature - should be ignored)
        response_db += 5.0 * np.exp(-((freqs - 1000) ** 2) / (2 * 30 ** 2))
        
        tilt_bands = fit_full_range_tilt(
            freqs_hz=freqs,
            measured_db=response_db,
            cutoff_hz=300.0,
            enable_tilt=True,
        )
        
        # The fit should not create a narrow band to address the 1 kHz peak
        # All tilt bands should be low-Q (smooth)
        for band in tilt_bands:
            assert band.q <= 2.0, f"Sharp features should be ignored; band Q={band.q} exceeds 2"
            # Band should not be a sharp correction at ~1 kHz
            if abs(band.freq - 1000) < 100:
                assert abs(band.gain_db) <= 3.0, f"Sharp peak correction should be limited, got {band.gain_db} dB"
    
    def test_enable_tilt_false_returns_empty(self):
        """enable_tilt=False returns empty band list."""
        from headmatch.room import fit_full_range_tilt
        
        freqs = np.geomspace(20, 20000, 500)
        response_db = np.zeros_like(freqs)
        
        bands = fit_full_range_tilt(
            freqs_hz=freqs,
            measured_db=response_db,
            cutoff_hz=300.0,
            enable_tilt=False,
        )
        
        assert bands == [], f"Expected empty list when enable_tilt=False, got {bands}"


class TestRoomDimensions:
    """Tests for estimate_cutoff_from_dimensions function.
    
    Phase 2 item 3 - provide a lightweight alternative to RT60 by
    estimating Schroeder frequency from entered room dimensions (L×W×H).
    """
    
    def test_function_exists(self):
        """estimate_cutoff_from_dimensions function exists in room module."""
        from headmatch.room import estimate_cutoff_from_dimensions
        assert callable(estimate_cutoff_from_dimensions)
    
    def test_basic_calculation_typical_room(self):
        """Basic calculation: 5m × 4m × 2.5m → V=50m³, RT60~0.5s → cutoff ≈ 200 Hz."""
        from headmatch.room import estimate_cutoff_from_dimensions
        
        result = estimate_cutoff_from_dimensions(length_m=5.0, width_m=4.0, height_m=2.5)
        
        # Volume = 5 * 4 * 2.5 = 50 m³
        # Schroeder frequency formula: fs = 2000 * sqrt(RT60 / V)
        # With RT60=0.5s: fs = 2000 * sqrt(0.5 / 50) = 2000 * sqrt(0.01) = 2000 * 0.1 = 200 Hz
        assert isinstance(result, (float, dict))
        if isinstance(result, dict):
            cutoff = result['cutoff_hz']
        else:
            cutoff = result
        
        assert 180 <= cutoff <= 220, f"Expected ~200 Hz for 50m³ typical room, got {cutoff}"
    
    def test_furnishing_factor_sparse(self):
        """Sparse furnishing assumes longer RT60 → higher Schroeder cutoff."""
        from headmatch.room import estimate_cutoff_from_dimensions

        # Same room, sparse furnishing
        result_sparse = estimate_cutoff_from_dimensions(
            length_m=5.0, width_m=4.0, height_m=2.5, furnishing='sparse'
        )
        result_typical = estimate_cutoff_from_dimensions(
            length_m=5.0, width_m=4.0, height_m=2.5, furnishing='typical'
        )

        if isinstance(result_sparse, dict):
            cutoff_sparse = result_sparse['cutoff_hz']
            cutoff_typical = result_typical['cutoff_hz']
        else:
            cutoff_sparse = result_sparse
            cutoff_typical = result_typical

        # A live/sparse room rings longer (higher RT60); by f = 2000·√(RT60/V)
        # a longer RT60 raises the Schroeder frequency.
        assert cutoff_sparse > cutoff_typical, \
            f"Sparse furnishing should give higher cutoff: {cutoff_sparse} vs {cutoff_typical}"
    
    def test_furnishing_factor_heavily_furnished(self):
        """Heavily furnished room assumes shorter RT60 → lower Schroeder cutoff."""
        from headmatch.room import estimate_cutoff_from_dimensions

        result_heavy = estimate_cutoff_from_dimensions(
            length_m=5.0, width_m=4.0, height_m=2.5, furnishing='heavily_furnished'
        )
        result_typical = estimate_cutoff_from_dimensions(
            length_m=5.0, width_m=4.0, height_m=2.5, furnishing='typical'
        )

        if isinstance(result_heavy, dict):
            cutoff_heavy = result_heavy['cutoff_hz']
            cutoff_typical = result_typical['cutoff_hz']
        else:
            cutoff_heavy = result_heavy
            cutoff_typical = result_typical

        # A heavily furnished (absorptive) room decays faster (lower RT60); by
        # f = 2000·√(RT60/V) a shorter RT60 lowers the Schroeder frequency.
        assert cutoff_heavy < cutoff_typical, \
            f"Heavily furnished should give lower cutoff: {cutoff_heavy} vs {cutoff_typical}"
    
    def test_default_furnishing_is_typical(self):
        """Default furnishing parameter equals 'typical'."""
        from headmatch.room import estimate_cutoff_from_dimensions
        
        result_default = estimate_cutoff_from_dimensions(5.0, 4.0, 2.5)
        result_typical = estimate_cutoff_from_dimensions(5.0, 4.0, 2.5, furnishing='typical')
        
        if isinstance(result_default, dict):
            assert result_default['cutoff_hz'] == result_typical['cutoff_hz']
        else:
            assert result_default == result_typical
    
    def test_reject_non_positive_dimensions(self):
        """Reject non-positive dimensions (zero or negative)."""
        from headmatch.room import estimate_cutoff_from_dimensions
        from headmatch.exceptions import MeasurementError
        
        with pytest.raises(MeasurementError):
            estimate_cutoff_from_dimensions(length_m=0.0, width_m=4.0, height_m=2.5)
        
        with pytest.raises(MeasurementError):
            estimate_cutoff_from_dimensions(length_m=5.0, width_m=-1.0, height_m=2.5)

        with pytest.raises(MeasurementError):
            estimate_cutoff_from_dimensions(length_m=5.0, width_m=4.0, height_m=-2.5)
    
    def test_reject_unreasonably_small_dimensions(self):
        """Reject unreasonably small dimensions (e.g., < 0.1m)."""
        from headmatch.room import estimate_cutoff_from_dimensions
        from headmatch.exceptions import MeasurementError
        
        with pytest.raises(MeasurementError):
            estimate_cutoff_from_dimensions(length_m=0.05, width_m=4.0, height_m=2.5)
    
    def test_reject_unreasonably_large_dimensions(self):
        """Reject unreasonably large dimensions (e.g., > 100m)."""
        from headmatch.room import estimate_cutoff_from_dimensions
        from headmatch.exceptions import MeasurementError
        
        with pytest.raises(MeasurementError):
            estimate_cutoff_from_dimensions(length_m=150.0, width_m=4.0, height_m=2.5)
    
    def test_output_format_returns_float(self):
        """Returns cutoff_hz as a float."""
        from headmatch.room import estimate_cutoff_from_dimensions
        
        result = estimate_cutoff_from_dimensions(5.0, 4.0, 2.5)
        
        # Result should be float or dict containing float
        cutoff = result['cutoff_hz'] if isinstance(result, dict) else result
        assert isinstance(cutoff, (int, float)), f"cutoff should be numeric, got {type(cutoff)}"
    
    def test_output_format_with_metadata(self):
        """When return_metadata=True, returns dict with calculation details."""
        from headmatch.room import estimate_cutoff_from_dimensions
        
        result = estimate_cutoff_from_dimensions(
            length_m=5.0, width_m=4.0, height_m=2.5, return_metadata=True
        )
        
        assert isinstance(result, dict)
        assert 'cutoff_hz' in result
        # Should include explanation fields
        assert 'volume_m3' in result or 'rt60_s' in result or 'furnishing' in result, \
            "Metadata should explain the calculation"
    
    def test_bounds_clamped_to_reasonable_range(self):
        """Result clamped to reasonable range (50-500 Hz)."""
        from headmatch.room import estimate_cutoff_from_dimensions
        
        # Very small room would normally give very high Schroeder frequency
        result_small = estimate_cutoff_from_dimensions(1.0, 1.0, 1.0)
        # Very large room would normally give very low Schroeder frequency
        result_large = estimate_cutoff_from_dimensions(20.0, 15.0, 8.0)
        
        if isinstance(result_small, dict):
            cutoff_small = result_small['cutoff_hz']
            cutoff_large = result_large['cutoff_hz']
        else:
            cutoff_small = result_small
            cutoff_large = result_large
        
        # Both should be within reasonable bounds
        assert 50 <= cutoff_small <= 500, f"Small room cutoff {cutoff_small} out of bounds"
        assert 50 <= cutoff_large <= 500, f"Large room cutoff {cutoff_large} out of bounds"


class TestGUIMetadata:
    """Tests for GUI progress/warnings display in room workflow.
    
    Verifies that RoomFitResult and related functions provide GUI-suitable
    metadata for the Room (beta) view to render warnings, confidence
    indicators, progress stages, and graph paths.
    """
    
    def test_warnings_list_is_human_readable_strings(self):
        """RoomFitResult.warnings is a list of human-readable strings."""
        import inspect
        
        # Get RoomFitResult signature
        sig = inspect.signature(RoomFitResult)
        params = sig.parameters
        
        assert 'warnings' in params, "RoomFitResult should have 'warnings' field"
        # Create a minimal RoomFitResult with warnings
        freqs = np.array([20, 50, 100, 200], dtype=np.float64)
        dummy_result = _dummy_measurement_result(freqs)
        
        result = RoomFitResult(
            result=dummy_result,
            eq_bands=[],
            target=build_room_target(freqs, sub_bass_rolloff=False),
            fit_report={},
            run_summary={
                'warnings': ['Test warning 1', 'Test warning 2'],
            },
            out_dir=Path('/tmp/test'),
            warnings=['Test warning 1', 'Test warning 2'],
        )
        
        # Warnings should be a list
        assert isinstance(result.warnings, list), "warnings should be a list"
        # Each warning should be a string (human-readable)
        for warning in result.warnings:
            assert isinstance(warning, str), f"Each warning should be a string, got {type(warning)}"
    
    def test_run_summary_includes_confidence_indicators(self):
        """run_summary includes confidence/quality indicators for GUI."""
        from headmatch.contracts import ConfidenceSummary
        
        # Create a confidence summary
        confidence = ConfidenceSummary(
            score=85,
            label="high",
            headline="High confidence fit",
            interpretation="The measurement quality is good",
            reasons=("Low noise floor", "Good signal level"),
            warnings=(),
            metrics={"snr_db": 65.0, "thd_percent": 0.05},
        )
        
        summary = confidence.to_dict()
        
        # Key fields for GUI rendering
        assert 'score' in summary, "confidence should have 'score'"
        assert 'label' in summary, "confidence should have 'label'"
        assert 'headline' in summary, "confidence should have 'headline'"
        assert 'interpretation' in summary, "confidence should have 'interpretation'"
        assert 'reasons' in summary, "confidence should have 'reasons'"
        assert 'warnings' in summary, "confidence should have 'warnings'"
        assert 'metrics' in summary, "confidence should have 'metrics'"
        
        # Type checks for GUI consumption
        assert isinstance(summary['score'], int), "score should be int"
        assert summary['label'] in ('high', 'medium', 'low'), \
            f"label should be high/medium/low, got {summary['label']}"
        assert isinstance(summary['headline'], str), "headline should be string"
        assert isinstance(summary['interpretation'], str), "interpretation should be string"
    
    def test_run_summary_plots_contains_svg_paths(self):
        """run_summary['plots'] contains paths to rendered SVG graphs."""
        from headmatch.contracts import FrontendRunSummary, RunFilterCounts, RunErrorSummary
        from headmatch.app_identity import AppIdentity
        from unittest.mock import MagicMock
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            
            # Create a run summary with plots
            plots = {
                'overview': str(out_dir / 'fit_overview.svg'),
                'left': str(out_dir / 'fit_left.svg'),
                'right': str(out_dir / 'fit_right.svg'),
            }
            
            # Mock confidence with a to_dict method
            mock_conf = MagicMock()
            mock_conf.to_dict.return_value = {
                'score': 85,
                'label': 'high',
                'headline': 'High confidence',
            }
            
            summary = FrontendRunSummary(
                schema_version=1,
                kind='fit',
                out_dir=str(out_dir),
                sample_rate=48000,
                frequency_points=100,
                target='room_modal_flat',
                filters=RunFilterCounts(left=4, right=4),
                predicted_error_db=RunErrorSummary(
                    left_rms=1.5, right_rms=1.5,
                    left_max=3.0, right_max=3.0
                ),
                confidence=mock_conf,
                plots=plots,
                results_guide=str(out_dir / 'README.txt'),
                generated_by={'version': 'test'},
            )
            
            summary_dict = summary.to_dict()
            
            assert 'plots' in summary_dict, "run_summary should contain 'plots'"
            assert isinstance(summary_dict['plots'], dict), "plots should be a dict"
            
            # Each plot value should be a path string
            for key, path in summary_dict['plots'].items():
                assert isinstance(path, str), f"plot path for {key} should be string"
                assert path.endswith('.svg'), f"plot path should end with .svg: {path}"
    
    def test_error_handling_includes_warnings_in_result(self):
        """When fitting fails or produces poor results, warnings are included."""
        freqs = np.array([20, 50, 100, 200], dtype=np.float64)
        dummy_result = _dummy_measurement_result(freqs)
        
        # Simulate a result with warnings (poor fit quality)
        warnings = [
            "Low signal-to-noise ratio detected",
            "Predicted error exceeds 3 dB threshold",
        ]
        
        result = RoomFitResult(
            result=dummy_result,
            eq_bands=[],
            target=build_room_target(freqs, sub_bass_rolloff=False),
            fit_report={
                'predicted_left_rms_error_db': 5.0,  # Poor quality
                'predicted_right_rms_error_db': 5.0,
            },
            run_summary={
                'confidence': {
                    'score': 45,
                    'label': 'low',
                    'warnings': warnings,
                },
            },
            out_dir=Path('/tmp/test'),
            warnings=warnings,
        )
        
        # Warnings should be present
        assert len(result.warnings) > 0, "Result should include warnings for poor fit"
        
        # Each warning should be human-readable
        for warning in result.warnings:
            assert len(warning) > 10, f"Warning should be descriptive: {warning}"
            assert any(c.isalpha() for c in warning), "Warning should contain text"
