"""Microphone calibration module for UMIK-1-style calibration files."""
from __future__ import annotations

import re
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy.interpolate import PchipInterpolator

# Constants
MIC_CAL_MIN_HZ = 20.0
MIC_CAL_MAX_HZ = 500.0
MIC_CAL_PLAUSIBLE_ABS_DB = 30.0


@dataclass
class MicCalibration:
    """Microphone calibration data.
    
    Attributes:
        freqs_hz: Frequency points in Hz
        gains_db: Calibration gains in dB (relative to nominal response)
        source: Path to the calibration file
    """
    freqs_hz: np.ndarray
    gains_db: np.ndarray
    source: str


def _split_line(line: str) -> list[str]:
    """Split a line by comma, tab, or whitespace."""
    # Try comma first
    if ',' in line:
        return [part.strip() for part in line.split(',')]
    # Try tab
    if '\t' in line:
        return [part.strip() for part in line.split('\t')]
    # Fall back to whitespace
    return line.split()


def _parse_value(val: str) -> float | None:
    """Parse a numeric value, returning None if invalid."""
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def load_mic_calibration(path: str | Path) -> MicCalibration:
    """Load a UMIK-1-style calibration file.
    
    Handles:
    - Comment lines (starting with * or #)
    - Sens Factor headers
    - Comma, tab, or whitespace separators
    - Column header lines
    
    Rejects files with implausible values (beyond ±30 dB) which indicate
    a wrong file type.
    
    Warns when calibration coverage doesn't span at least 20-500 Hz.
    
    Absolute SPL / Sens Factor lines are parsed past and discarded.
    Only relative FR data is returned.
    
    Args:
        path: Path to the calibration file
        
    Returns:
        MicCalibration: The loaded calibration data
        
    Raises:
        ValueError: If the file cannot be parsed or contains implausible values
    """
    path = Path(path)
    freqs: list[float] = []
    gains: list[float] = []
    
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Skip comment lines (UMIK-style)
            if line.startswith('*') or line.startswith('#'):
                continue
            
            # Skip absolute Sens Factor line (e.g., "Sens Factor = -2.3 dB")
            if 'Sens Factor' in line:
                continue
            
            # Skip column header lines (e.g., "Freq(Hz), SPL(dB)")
            if 'Hz' in line.lower() and ('SPL' in line or 'dB' in line or 'Cal' in line):
                # Check if it looks like a header, not data
                parts = _split_line(line)
                if any(c.isalpha() for c in line) and not any(_parse_value(p) is not None for p in parts if not any(c.isalpha() for c in p)):
                    continue
            
            # Parse data line
            parts = _split_line(line)
            if len(parts) < 2:
                continue
            
            freq = _parse_value(parts[0])
            gain = _parse_value(parts[1])
            
            if freq is None or gain is None:
                continue
            
            freqs.append(freq)
            gains.append(gain)
    
    if len(freqs) < 2:
        raise ValueError(f"Calibration file '{path}' must contain at least 2 data points")
    
    freqs_arr = np.array(freqs, dtype=float)
    gains_arr = np.array(gains, dtype=float)
    
    # Sort by frequency
    sort_idx = np.argsort(freqs_arr)
    freqs_arr = freqs_arr[sort_idx]
    gains_arr = gains_arr[sort_idx]
    
    # Check for implausible values (beyond ±30 dB)
    if np.any(np.abs(gains_arr) > MIC_CAL_PLAUSIBLE_ABS_DB):
        raise ValueError(
            f"Calibration file '{path}' contains implausible values "
            f"(beyond ±{MIC_CAL_PLAUSIBLE_ABS_DB} dB). "
            "This may indicate a wrong file type."
        )
    
    # Warn on insufficient coverage
    min_freq = np.min(freqs_arr)
    max_freq = np.max(freqs_arr)
    if min_freq > MIC_CAL_MIN_HZ or max_freq < MIC_CAL_MAX_HZ:
        warnings.warn(
            f"Calibration coverage may be insufficient: "
            f"file spans {min_freq:.1f} Hz to {max_freq:.1f} Hz, "
            f"but 20-500 Hz is recommended.",
            UserWarning
        )
    
    return MicCalibration(freqs_hz=freqs_arr, gains_db=gains_arr, source=str(path))


def calibration_offset(cal: MicCalibration, freq_grid: np.ndarray) -> np.ndarray:
    """Compute calibration offset at specified frequencies using PCHIP interpolation.
    
    Uses PCHIP interpolation onto the frequency grid, holding the calibration
    flat (constant) outside the calibration range.
    
    Args:
        cal: MicCalibration object with frequency and gain data
        freq_grid: Array of frequencies in Hz to interpolate to
        
    Returns:
        Array of calibration gains in dB at the specified frequencies
    """
    if len(cal.freqs_hz) == 0:
        return np.zeros_like(freq_grid, dtype=float)
    
    # Handle edge case: single point calibration
    if len(cal.freqs_hz) == 1:
        return np.full_like(freq_grid, cal.gains_db[0], dtype=float)
    
    # Create PCHIP interpolator
    interpolator = PchipInterpolator(cal.freqs_hz, cal.gains_db, extrapolate=False)
    
    # Interpolate
    result = interpolator(freq_grid.astype(float))
    
    # Handle extrapolation: hold flat outside the calibration range
    if np.any(freq_grid < cal.freqs_hz[0]):
        result[freq_grid < cal.freqs_hz[0]] = cal.gains_db[0]
    if np.any(freq_grid > cal.freqs_hz[-1]):
        result[freq_grid > cal.freqs_hz[-1]] = cal.gains_db[-1]
    
    return result