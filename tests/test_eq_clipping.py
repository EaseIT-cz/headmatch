"""Tests for EQ clipping prediction module."""

import numpy as np
import pytest

from headmatch.eq_clipping import (
    EQClippingAssessment,
    assess_eq_clipping,
    format_clipping_assessment,
    format_clipping_summary,
)
from headmatch.peq import PEQBand


class TestAssessEQClipping:
    """Tests for assess_eq_clipping function."""
    
    @pytest.fixture
    def sample_rate(self):
        return 48000
    
    @pytest.fixture
    def freqs(self):
        return np.logspace(np.log10(20), np.log10(20000), 500)
    
    def test_no_bands_no_clipping(self, freqs, sample_rate):
        """Empty EQ profile should report no clipping."""
        result = assess_eq_clipping(freqs, sample_rate, [], [])
        
        assert result.will_clip is False
        assert result.left_peak_boost_db == pytest.approx(0.0, abs=0.01)
        assert result.right_peak_boost_db == pytest.approx(0.0, abs=0.01)
        assert result.total_preamp_db == pytest.approx(0.0, abs=0.01)
        assert result.headroom_loss_db == pytest.approx(0.0, abs=0.01)
        assert result.quality_concern is None
    
    def test_positive_boost_will_clip(self, freqs, sample_rate):
        """EQ with positive boost should report clipping risk."""
        # Create a +6 dB boost at 1000 Hz
        bands = [PEQBand("peaking", 1000.0, 6.0, 1.0)]
        
        result = assess_eq_clipping(freqs, sample_rate, bands, bands)
        
        assert result.will_clip is True
        assert result.left_peak_boost_db == pytest.approx(6.0, abs=0.5)
        assert result.right_peak_boost_db == pytest.approx(6.0, abs=0.5)
        assert result.total_preamp_db == pytest.approx(-6.0, abs=0.5)
        assert result.headroom_loss_db == pytest.approx(6.0, abs=0.5)
    
    def test_negative_boost_no_clipping(self, freqs, sample_rate):
        """EQ with only negative gain (cuts) should not clip."""
        # Create a -6 dB cut at 1000 Hz
        bands = [PEQBand("peaking", 1000.0, -6.0, 1.0)]
        
        result = assess_eq_clipping(freqs, sample_rate, bands, bands)
        
        assert result.will_clip is False
        assert result.left_peak_boost_db < 0.1  # Near zero or negative
        assert result.total_preamp_db == pytest.approx(0.0, abs=0.1)
    
    def test_mixed_boost_evaulates_peak(self, freqs, sample_rate):
        """EQ with mixed boosts and cuts should evaluate the peak boost."""
        # +4 dB at 100 Hz, -3 dB at 1000 Hz, +6 dB at 5000 Hz
        bands = [
            PEQBand("peaking", 100.0, 4.0, 1.0),
            PEQBand("peaking", 1000.0, -3.0, 1.0),
            PEQBand("peaking", 5000.0, 6.0, 1.0),
        ]
        
        result = assess_eq_clipping(freqs, sample_rate, bands, bands)
        
        assert result.will_clip is True
        # Peak should be around 6 dB (max positive boost)
        assert result.left_peak_boost_db > 5.0
        assert result.total_preamp_db < -5.0
    
    def test_different_left_right_channels(self, freqs, sample_rate):
        """Left and right channels can have different clipping risk."""
        # Left: +3 dB boost
        # Right: +9 dB boost
        left_bands = [PEQBand("peaking", 1000.0, 3.0, 1.0)]
        right_bands = [PEQBand("peaking", 1000.0, 9.0, 1.0)]
        
        result = assess_eq_clipping(freqs, sample_rate, left_bands, right_bands)
        
        assert result.left_peak_boost_db == pytest.approx(3.0, abs=0.5)
        assert result.right_peak_boost_db == pytest.approx(9.0, abs=0.5)
        # Total preamp is the max (most negative) needed
        assert result.total_preamp_db == pytest.approx(-9.0, abs=0.5)
    
    def test_moderate_headroom_loss_warning(self, freqs, sample_rate):
        """Moderate headroom loss (>6 dB) should have a quality concern."""
        # +8 dB boost
        bands = [PEQBand("peaking", 1000.0, 8.0, 1.0)]
        
        result = assess_eq_clipping(freqs, sample_rate, bands, bands)
        
        assert result.will_clip is True
        assert result.headroom_loss_db == pytest.approx(8.0, abs=0.5)
        assert result.quality_concern is not None
        assert "Moderate" in result.quality_concern
    
    def test_severe_headroom_loss_warning(self, freqs, sample_rate):
        """Severe headroom loss (>12 dB) should have a severe quality concern."""
        # +15 dB boost
        bands = [PEQBand("peaking", 1000.0, 15.0, 1.0)]
        
        result = assess_eq_clipping(freqs, sample_rate, bands, bands)
        
        assert result.will_clip is True
        assert result.headroom_loss_db == pytest.approx(15.0, abs=0.5)
        assert result.quality_concern is not None
        assert "Severe" in result.quality_concern


class TestFormatClippingAssessment:
    """Tests for format_clipping_assessment function."""
    
    def test_format_no_clipping(self):
        """No clipping should produce OK message."""
        assessment = EQClippingAssessment(
            left_peak_boost_db=0.0,
            right_peak_boost_db=0.0,
            left_preamp_db=0.0,
            right_preamp_db=0.0,
            total_preamp_db=0.0,
            will_clip=False,
            headroom_loss_db=0.0,
            quality_concern=None,
        )
        
        output = format_clipping_assessment(assessment)
        
        assert "No positive boost" in output
        assert "no preamp needed" in output
    
    def test_format_with_clipping(self):
        """Clipping should produce warning message."""
        assessment = EQClippingAssessment(
            left_peak_boost_db=6.0,
            right_peak_boost_db=6.0,
            left_preamp_db=-6.0,
            right_preamp_db=-6.0,
            total_preamp_db=-6.0,
            will_clip=True,
            headroom_loss_db=6.0,
            quality_concern=None,
        )
        
        output = format_clipping_assessment(assessment)
        
        assert "Positive boost detected" in output
        assert "preamp required" in output
        assert "+6.0 dB" in output
        assert "-6.0 dB" in output
    
    def test_format_includes_quality_concern(self):
        """Output should include quality concern if present."""
        assessment = EQClippingAssessment(
            left_peak_boost_db=10.0,
            right_peak_boost_db=10.0,
            left_preamp_db=-10.0,
            right_preamp_db=-10.0,
            total_preamp_db=-10.0,
            will_clip=True,
            headroom_loss_db=10.0,
            quality_concern="Moderate headroom loss",
        )
        
        output = format_clipping_assessment(assessment)
        
        assert "headroom loss" in output.lower()


class TestFormatClippingSummary:
    """Tests for format_clipping_summary function."""
    
    def test_summary_no_clipping(self):
        """No clipping summary should show OK."""
        assessment = EQClippingAssessment(
            left_peak_boost_db=0.0,
            right_peak_boost_db=0.0,
            left_preamp_db=0.0,
            right_preamp_db=0.0,
            total_preamp_db=0.0,
            will_clip=False,
            headroom_loss_db=0.0,
            quality_concern=None,
        )
        
        summary = format_clipping_summary(assessment)
        
        assert "OK" in summary
    
    def test_summary_with_clipping(self):
        """Clipping summary should show preamp needed."""
        assessment = EQClippingAssessment(
            left_peak_boost_db=6.0,
            right_peak_boost_db=6.0,
            left_preamp_db=-6.0,
            right_preamp_db=-6.0,
            total_preamp_db=-6.0,
            will_clip=True,
            headroom_loss_db=6.0,
            quality_concern=None,
        )
        
        summary = format_clipping_summary(assessment)
        
        assert "preamp -6.0 dB" in summary
        assert "peak boost 6.0 dB" in summary


class TestEQClippingIntegration:
    """Integration tests with PEQ fitting."""
    
    def test_assess_after_fit(self, tmp_path):
        """Clipping assessment should work with bands from actual fit."""
        from headmatch.peq import fit_peq
        
        # Create a measurement with a dip at 100 Hz
        freqs = np.logspace(np.log10(20), np.log10(20000), 500)
        # EQ target: boost at 100 Hz to fix a dip
        eq_target = np.zeros_like(freqs)
        eq_target[freqs < 200] = 6.0  # +6 dB boost needed at low frequencies
        
        sample_rate = 48000
        bands = fit_peq(freqs, eq_target, sample_rate, max_filters=4)
        
        # Assess clipping
        result = assess_eq_clipping(freqs, sample_rate, bands, bands)
        
        # The fit may or may not have positive boost depending on the fit quality
        # Just check that the assessment runs without error
        assert isinstance(result, EQClippingAssessment)
        assert result.left_peak_boost_db == result.right_peak_boost_db  # Same bands used
