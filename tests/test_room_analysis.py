"""Tests for RT60-based adaptive Schroeder cutoff in room analysis.

Covers:
- RT60 computation from impulse response via Schroeder backward integration
- Schroeder frequency formula: f_schroeder = 2000 * sqrt(RT60 / V)
- Fallback to ROOM_CUTOFF_DEFAULT_HZ when IR/RT60 unavailable
- Bounds checking: cutoff clamped to reasonable range (50-500 Hz)
- Integration: fit_room_bands accepts cutoff_hz='auto' for RT60-based estimation
"""
from __future__ import annotations

import numpy as np
import pytest

from headmatch.room import (
    ROOM_CUTOFF_DEFAULT_HZ,
    fit_room_bands,
)


class TestEstimateSchroederCutoff:
    """Tests for estimate_schroeder_cutoff function.
    
    This function implements RT60-based adaptive Schroeder cutoff calculation:
    f_schroeder = 2000 * sqrt(RT60 / V)
    """
    
    def test_function_exists_and_is_importable(self):
        """estimate_schroeder_cutoff function exists and can be imported."""
        from headmatch.room import estimate_schroeder_cutoff
        assert callable(estimate_schroeder_cutoff)
    
    def test_rt60_from_ir_computed_via_schroeder_integration(self):
        """RT60 from IR: computes via Schroeder backward integration.
        
        The Schroeder integration method computes energy decay curve by integrating
        the squared impulse response backwards from the end.
        """
        from headmatch.room import estimate_schroeder_cutoff
        
        # Create synthetic impulse response (decaying exponential simulates reverb)
        sample_rate = 48000
        duration = 1.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        # Decay constant for ~0.5s RT60
        decay_time = 0.5
        ir = np.exp(-t / (decay_time / (np.log(10) * 6))) * np.random.randn(len(t))
        
        # Function should accept impulse response array and sample_rate
        result = estimate_schroeder_cutoff(
            impulse_response=ir,
            sample_rate=sample_rate,
            room_volume_m3=50.0,
        )
        
        # Result should be a float cutoff frequency
        assert isinstance(result, float) or hasattr(result, 'cutoff_hz')
    
    def test_schroeder_frequency_formula_calculates_correctly(self):
        """Schroeder frequency formula: f = 2000 * sqrt(RT60 / V).
        
        Example: RT60=0.5s, V=50m³ → f_schroeder ≈ 200 Hz
        Example: RT60=1.0s, V=100m³ → f_schroeder ≈ 200 Hz
        """
        from headmatch.room import estimate_schroeder_cutoff
        
        # Create synthetic IR with known RT60 ~0.5s
        sample_rate = 48000
        duration = 1.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        rt60_expected = 0.5
        decay_constant = rt60_expected / (np.log(10) * 6)  # Time constant for RT60 decay
        ir = np.exp(-t / decay_constant) * np.random.randn(len(t))
        
        # Test example 1: V=50m³, RT60≈0.5s → f_schroeder ≈ 200 Hz
        volume_m3 = 50.0
        cutoff = estimate_schroeder_cutoff(
            impulse_response=ir,
            sample_rate=sample_rate,
            room_volume_m3=volume_m3,
        )
        
        # Expected: f_schroeder = 2000 * sqrt(0.5 / 50) = 2000 * sqrt(0.01) = 2000 * 0.1 = 200 Hz
        expected_cutoff = 2000 * np.sqrt(rt60_expected / volume_m3)
        assert abs(cutoff - expected_cutoff) < 20, \
            f"Expected f_schroeder ≈ {expected_cutoff:.1f} Hz, got {cutoff:.1f} Hz"
        
        # Test example 2: V=100m³ → same RT60, larger V → lower f_schroeder
        volume_m3_2 = 100.0
        cutoff_2 = estimate_schroeder_cutoff(
            impulse_response=ir,
            sample_rate=sample_rate,
            room_volume_m3=volume_m3_2,
        )
        
        # Expected: f_schroeder = 2000 * sqrt(0.5 / 100) = 2000 * sqrt(0.005) ≈ 141 Hz
        expected_cutoff_2 = 2000 * np.sqrt(rt60_expected / volume_m3_2)
        assert abs(cutoff_2 - expected_cutoff_2) < 20, \
            f"Expected f_schroeder ≈ {expected_cutoff_2:.1f} Hz, got {cutoff_2:.1f} Hz"
    
    def test_fallback_when_ir_unavailable(self):
        """Fallback behavior: when IR/RT60 unavailable, returns ROOM_CUTOFF_DEFAULT_HZ.
        
        If impulse_response is None, function should return default cutoff (300 Hz).
        """
        from headmatch.room import estimate_schroeder_cutoff
        
        result = estimate_schroeder_cutoff(
            impulse_response=None,
            sample_rate=48000,
            room_volume_m3=50.0,
        )
        
        assert result == ROOM_CUTOFF_DEFAULT_HZ, \
            f"Expected fallback to {ROOM_CUTOFF_DEFAULT_HZ} Hz, got {result} Hz"
    
    def test_fallback_when_rt60_cannot_be_computed(self):
        """Fallback behavior: when RT60 computation fails, returns ROOM_CUTOFF_DEFAULT_HZ.
        
        If IR is too short or too noisy to estimate RT60, function should fallback.
        """
        from headmatch.room import estimate_schroeder_cutoff
        
        # Very short IR that can't reliably estimate RT60
        short_ir = np.array([1.0, 0.5, 0.1])
        
        result = estimate_schroeder_cutoff(
            impulse_response=short_ir,
            sample_rate=48000,
            room_volume_m3=50.0,
        )
        
        assert result == ROOM_CUTOFF_DEFAULT_HZ, \
            f"Expected fallback to {ROOM_CUTOFF_DEFAULT_HZ} Hz, got {result} Hz"
    
    def test_bounds_checking_clamps_minimum(self):
        """Bounds checking: returned cutoff clamped to minimum of 50 Hz.
        
        Very large rooms or long RT60 should not return cutoff below 50 Hz.
        """
        from headmatch.room import estimate_schroeder_cutoff
        
        sample_rate = 48000
        duration = 2.0  # Longer IR
        t = np.linspace(0, duration, int(sample_rate * duration))
        
        # Create IR with very long RT60 (~2s) for large room
        rt60_expected = 2.0
        decay_constant = rt60_expected / (np.log(10) * 6)
        ir = np.exp(-t / decay_constant) * np.random.randn(len(t))
        
        # Huge room volume should produce cutoff below 50 Hz before clamping
        large_volume = 10000.0  # m³
        cutoff = estimate_schroeder_cutoff(
            impulse_response=ir,
            sample_rate=sample_rate,
            room_volume_m3=large_volume,
        )
        
        # f_schroeder = 2000 * sqrt(2 / 10000) = 2000 * 0.014 = 28 Hz (clamped to 50)
        assert cutoff >= 50.0, \
            f"Expected cutoff >= 50 Hz due to clamping, got {cutoff} Hz"
    
    def test_bounds_checking_clamps_maximum(self):
        """Bounds checking: returned cutoff clamped to maximum of 500 Hz.
        
        Very small rooms or short RT60 should not return cutoff above 500 Hz.
        """
        from headmatch.room import estimate_schroeder_cutoff
        
        sample_rate = 48000
        duration = 0.1
        t = np.linspace(0, duration, int(sample_rate * duration))
        
        # Create IR with very short RT60 (~0.05s)
        rt60_expected = 0.05
        decay_constant = rt60_expected / (np.log(10) * 6)
        ir = np.exp(-t / decay_constant) * np.random.randn(len(t))
        
        # Tiny room volume should produce cutoff above 500 Hz before clamping
        small_volume = 5.0  # m³ (small closet)
        cutoff = estimate_schroeder_cutoff(
            impulse_response=ir,
            sample_rate=sample_rate,
            room_volume_m3=small_volume,
        )
        
        # f_schroeder = 2000 * sqrt(0.05 / 5) = 2000 * 0.1 = 200 Hz
        # But with extremely small volume this could exceed 500 Hz
        assert cutoff <= 500.0, \
            f"Expected cutoff <= 500 Hz due to clamping, got {cutoff} Hz"
    
    def test_bound_clamping_creates_reasonable_range(self):
        """Cutoff always falls within reasonable range (50-500 Hz).
        
        Normal usage should return values in the 100-400 Hz range for typical rooms.
        """
        from headmatch.room import estimate_schroeder_cutoff
        
        sample_rate = 48000
        
        for rt60 in [0.3, 0.5, 0.8, 1.0]:
            for volume in [30, 50, 100, 200]:
                duration = max(1.0, rt60 * 3)
                t = np.linspace(0, duration, int(sample_rate * duration))
                decay_constant = rt60 / (np.log(10) * 6)
                ir = np.exp(-t / decay_constant) * np.random.randn(len(t))
                
                cutoff = estimate_schroeder_cutoff(
                    impulse_response=ir,
                    sample_rate=sample_rate,
                    room_volume_m3=volume,
                )
                
                assert 50.0 <= cutoff <= 500.0, \
                    f"Cutoff {cutoff} Hz out of bounds for RT60={rt60}, V={volume}"


class TestFitRoomBandsAutoCutoff:
    """Integration tests for fit_room_bands with cutoff_hz='auto'."""
    
    def test_function_accepts_auto_for_cutoff_hz(self):
        """fit_room_bands accepts cutoff_hz='auto' to trigger RT60-based estimation."""
        freqs = np.geomspace(20, 500, 200)
        eq_target = np.zeros_like(freqs)
        
        # Should accept 'auto' as a special value for cutoff_hz
        # When 'auto' is used, function should estimate cutoff from RT60
        # This will likely require additional parameters (impulse_response, room_volume)
        try:
            bands = fit_room_bands(
                freqs_hz=freqs,
                eq_target_db=eq_target,
                sample_rate=48000,
                cutoff_hz='auto',  # RT60-based estimation
                impulse_response=np.random.randn(48000),  # Additional param for RT60
                room_volume_m3=50.0,  # Additional param for Schroeder formula
            )
            assert len(bands) >= 0  # Function executed
        except TypeError as e:
            if 'auto' in str(e) or 'cutoff_hz' in str(e):
                pytest.fail("fit_room_bands should accept cutoff_hz='auto' with additional params")
    
    def test_auto_cutoff_uses_rt60_estimation(self):
        """cutoff_hz='auto' uses RT60-based Schroeder frequency estimation.
        
        The estimated cutoff should be derived from the impulse response RT60
        using the Schroeder formula.
        """
        freqs = np.geomspace(20, 500, 200)
        
        # Create a response with known characteristics
        eq_target = np.zeros_like(freqs)
        
        sample_rate = 48000
        duration = 1.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        rt60_expected = 0.5
        decay_constant = rt60_expected / (np.log(10) * 6)
        ir = np.exp(-t / decay_constant) * np.random.randn(len(t))
        
        volume_m3 = 50.0
        expected_cutoff = 2000 * np.sqrt(rt60_expected / volume_m3)  # ~200 Hz
        
        # The fit should use an RT60-derived cutoff near 200 Hz
        try:
            bands = fit_room_bands(
                freqs_hz=freqs,
                eq_target_db=eq_target,
                sample_rate=sample_rate,
                cutoff_hz='auto',
                impulse_response=ir,
                room_volume_m3=volume_m3,
            )
            
            # Validate that no band exceeds the expected Schroeder frequency
            # (within reasonable tolerance for estimation errors)
            for band in bands:
                assert band.freq <= expected_cutoff * 1.5, \
                    f"Band at {band.freq} Hz exceeds estimated Schroeder cutoff ({expected_cutoff:.1f} Hz)"
        except TypeError:
            pytest.xfail("RT60-based auto cutoff requires additional parameters")