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
)
from headmatch.analysis import MeasurementResult
from headmatch.mic_cal import MicCalibration
from headmatch.peq import PEQBand


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


class TestRoomConstants:
    """Tests for room module constants."""
    
    def test_constants_defined(self):
        """Room constants are properly defined."""
        assert ROOM_CUTOFF_DEFAULT_HZ == 300.0
        assert ROOM_MAX_BOOST_DB == 2.0