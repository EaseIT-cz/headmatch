"""Tests for mic_cal.py — TASK-117: Microphone calibration module."""
from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pytest

from headmatch.exceptions import ConfigError
from headmatch.mic_cal import (
    MIC_CAL_MAX_HZ,
    MIC_CAL_MIN_HZ,
    MIC_CAL_PLAUSIBLE_ABS_DB,
    MicCalibration,
    calibration_offset,
    load_mic_calibration,
)


class TestParsesUmikStyle:
    """Test parsing UMIK-1-style calibration files."""

    def test_parses_umik_style_with_sens_factor_and_comments(self, tmp_path: Path) -> None:
        """Test parsing UMIK-style file with Sens Factor header and comment lines."""
        cal_path = tmp_path / "umik_cal.txt"
        cal_content = """* UMIK-1 Calibration File
* Serial: 12345
Sens Factor = -18.00 dB
* Freq(Hz), SPL(dB)
10, 0.5
20, 0.3
* This is a comment
100, 0.0
1000, -0.2
20000, -0.5
"""
        cal_path.write_text(cal_content)
        
        cal = load_mic_calibration(cal_path)
        
        assert cal.source == str(cal_path)
        assert len(cal.freqs_hz) == 5
        assert len(cal.gains_db) == 5
        # Verify data points
        np.testing.assert_array_almost_equal(cal.freqs_hz, np.array([10, 20, 100, 1000, 20000]))
        np.testing.assert_array_almost_equal(cal.gains_db, np.array([0.5, 0.3, 0.0, -0.2, -0.5]))

    def test_tolerates_column_header_line(self, tmp_path: Path) -> None:
        """Test that column headers like 'Freq(Hz), SPL(dB)' are skipped."""
        cal_path = tmp_path / "umik_cal.txt"
        cal_content = """"Freq(Hz)" "SPL(dB)"
20, 0.3
100, 0.0
1000, -0.2
"""
        cal_path.write_text(cal_content)
        
        cal = load_mic_calibration(cal_path)
        
        assert len(cal.freqs_hz) == 3
        assert len(cal.gains_db) == 3
        np.testing.assert_array_almost_equal(cal.freqs_hz, np.array([20, 100, 1000]))
        np.testing.assert_array_almost_equal(cal.gains_db, np.array([0.3, 0.0, -0.2]))

    def test_handles_tab_separator(self, tmp_path: Path) -> None:
        """Test parsing tab-separated files."""
        cal_path = tmp_path / "umik_cal.txt"
        cal_content = "20\t0.3\n100\t0.0\n1000\t-0.2\n"
        cal_path.write_text(cal_content)
        
        cal = load_mic_calibration(cal_path)
        
        assert len(cal.freqs_hz) == 3
        np.testing.assert_array_almost_equal(cal.freqs_hz, np.array([20, 100, 1000]))
        np.testing.assert_array_almost_equal(cal.gains_db, np.array([0.3, 0.0, -0.2]))

    def test_handles_whitespace_separator(self, tmp_path: Path) -> None:
        """Test parsing whitespace-separated files."""
        cal_path = tmp_path / "umik_cal.txt"
        cal_content = "20 0.3\n100 0.0\n1000 -0.2\n"
        cal_path.write_text(cal_content)
        
        cal = load_mic_calibration(cal_path)
        
        assert len(cal.freqs_hz) == 3
        np.testing.assert_array_almost_equal(cal.freqs_hz, np.array([20, 100, 1000]))
        np.testing.assert_array_almost_equal(cal.gains_db, np.array([0.3, 0.0, -0.2]))


class TestRejectsImplausible:
    """Test rejection of files with implausible values."""

    def test_rejects_implausible_scale(self, tmp_path: Path) -> None:
        """Test that files with values beyond ±30 dB are rejected."""
        cal_path = tmp_path / "bad_cal.txt"
        cal_content = """20, 0.3
100, 40.0
1000, -35.0
"""
        cal_path.write_text(cal_content)

        with pytest.raises(ConfigError) as exc_info:
            load_mic_calibration(cal_path)

        assert "implausible" in str(exc_info.value).lower()
        assert "beyond ±30" in str(exc_info.value)


class TestWarnsCoverage:
    """Test warning for insufficient frequency coverage."""

    def test_warns_when_coverage_insufficient(self, tmp_path: Path) -> None:
        """Test warning when calibration doesn't cover 20-500 Hz."""
        cal_path = tmp_path / "limited_cal.txt"
        cal_content = """25, 0.3
100, 0.0
400, -0.2
"""
        cal_path.write_text(cal_content)
        
        # min is 25 > MIC_CAL_MIN_HZ (20), so should warn
        with pytest.warns(UserWarning) as warning_list:
            cal = load_mic_calibration(cal_path)
        
        assert len(warning_list) == 1
        assert "coverage" in str(warning_list[0].message).lower()
        assert "insufficient" in str(warning_list[0].message).lower()
        assert "20-500" in str(warning_list[0].message)

    def test_no_warning_for_good_coverage(self, tmp_path: Path) -> None:
        """Test no warning when calibration covers 20-500 Hz."""
        cal_path = tmp_path / "good_cal.txt"
        cal_content = """10, 0.5
20, 0.3
500, 0.0
1000, -0.2
"""
        cal_path.write_text(cal_content)
        
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            cal = load_mic_calibration(cal_path)  # Should not raise

    def test_warns_when_max_insufficient(self, tmp_path: Path) -> None:
        """Test warning when calibration max is below 500 Hz."""
        cal_path = tmp_path / "low_max_cal.txt"
        cal_content = """10, 0.5
20, 0.3
300, 0.0
400, -0.2
"""
        cal_path.write_text(cal_content)
        
        with pytest.warns(UserWarning) as warning_list:
            cal = load_mic_calibration(cal_path)
        
        assert len(warning_list) == 1
        assert "coverage" in str(warning_list[0].message).lower()


class TestOffsetInterpolation:
    """Test calibration offset interpolation."""

    def test_offset_interpolates_and_holds_flat_outside_range(self, tmp_path: Path) -> None:
        """Test that PCHIP interpolation is used and holds flat outside range."""
        # Create calibration with known points
        cal = MicCalibration(
            freqs_hz=np.array([100, 200, 400]),
            gains_db=np.array([1.0, 2.0, 3.0]),
            source="test"
        )
        
        # Test interpolation within range
        freq_grid = np.array([50, 100, 150, 200, 300, 400, 500])
        offsets = calibration_offset(cal, freq_grid)
        
        # Below min: should hold flat at first gain
        assert offsets[0] == 1.0  # 50 Hz < 100 Hz, so hold at 1.0
        
        # At exact points
        assert offsets[1] == 1.0  # 100 Hz
        assert offsets[3] == 2.0  # 200 Hz
        assert offsets[5] == 3.0  # 400 Hz
        
        # Above max: should hold flat at last gain
        assert offsets[6] == 3.0  # 500 Hz > 400 Hz, so hold at 3.0

    def test_single_point_calibration(self) -> None:
        """Test calibration with only one data point."""
        cal = MicCalibration(
            freqs_hz=np.array([100]),
            gains_db=np.array([2.5]),
            source="test"
        )
        
        freq_grid = np.array([50, 100, 200])
        offsets = calibration_offset(cal, freq_grid)
        
        # All points should get the same gain
        np.testing.assert_array_almost_equal(offsets, np.array([2.5, 2.5, 2.5]))

    def test_empty_calibration_returns_zeros(self) -> None:
        """Test that empty calibration returns zeros."""
        cal = MicCalibration(
            freqs_hz=np.array([]),
            gains_db=np.array([]),
            source="test"
        )
        
        freq_grid = np.array([50, 100, 200])
        offsets = calibration_offset(cal, freq_grid)
        
        np.testing.assert_array_almost_equal(offsets, np.array([0.0, 0.0, 0.0]))

    def test_pchip_monotonic_preservation(self) -> None:
        """Test that PCHIP preserves monotonicity of data."""
        cal = MicCalibration(
            freqs_hz=np.array([100, 200, 400]),
            gains_db=np.array([0.0, 1.0, 0.5]),
            source="test"
        )
        
        freq_grid = np.array([150, 250, 300, 350])
        offsets = calibration_offset(cal, freq_grid)
        
        # Interpolated points should be within range of calibration data
        assert np.all(offsets >= -0.1)  # Slightly below min gain
        assert np.all(offsets <= 1.1)   # Slightly above max gain