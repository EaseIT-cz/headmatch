"""TASK-064: RBJ reference coefficient tests + TASK-065: numerical stability tests."""
from __future__ import annotations

import numpy as np
import pytest

from headmatch.peq import PEQBand, biquad_response_db


# ---------------------------------------------------------------------------
# TASK-064: RBJ reference verification
# ---------------------------------------------------------------------------

FC_VALUES = [30, 100, 1000, 5000, 15000]
Q_VALUES = [0.3, 0.707, 2.0, 8.0]
GAIN_VALUES = [-12, -3, 0, 3, 12]
FS_VALUES = [44100, 48000, 96000]
FILTER_TYPES = ["peaking", "lowshelf", "highshelf"]


@pytest.mark.parametrize("kind", FILTER_TYPES)
@pytest.mark.parametrize("fs", FS_VALUES)
@pytest.mark.parametrize("gain_db", [0.0])
def test_zero_gain_produces_flat_response(kind, fs, gain_db):
    """A filter with 0 dB gain should produce a flat (0 dB) response."""
    freqs = np.geomspace(20, min(fs / 2 - 1, 20000), 200)
    band = PEQBand(kind, 1000.0, gain_db, 1.0)
    response = biquad_response_db(freqs, fs, band)
    assert np.all(np.isfinite(response))
    assert np.max(np.abs(response)) < 0.01, f"Zero-gain {kind} should be flat, got max {np.max(np.abs(response)):.4f} dB"


@pytest.mark.parametrize("fc", FC_VALUES)
@pytest.mark.parametrize("q", Q_VALUES)
@pytest.mark.parametrize("gain_db", GAIN_VALUES)
@pytest.mark.parametrize("fs", [48000])
def test_peaking_peak_gain_near_center_frequency(fc, q, gain_db, fs):
    """A peaking filter's response at its center frequency should be close to the requested gain."""
    if fc >= fs / 2:
        pytest.skip("Fc above Nyquist")
    if gain_db == 0:
        return  # covered by zero-gain test
    freqs = np.array([float(fc)])
    band = PEQBand("peaking", float(fc), float(gain_db), float(q))
    response = biquad_response_db(freqs, fs, band)
    assert np.all(np.isfinite(response))
    # At center frequency, gain should be very close to requested gain
    assert abs(response[0] - gain_db) < 0.5, f"Peaking at Fc={fc}, Q={q}, gain={gain_db}: got {response[0]:.2f} dB"


@pytest.mark.parametrize("fc", [100, 1000, 5000])
@pytest.mark.parametrize("gain_db", [-6, 6])
@pytest.mark.parametrize("fs", FS_VALUES)
def test_shelf_asymptotic_gain(fc, gain_db, fs):
    """Shelf filters should approach requested gain far from the corner frequency."""
    if fc >= fs / 2:
        pytest.skip("Fc above Nyquist")
    for kind in ("lowshelf", "highshelf"):
        band = PEQBand(kind, float(fc), float(gain_db), 0.7)
        if kind == "lowshelf":
            # Check gain well below corner frequency
            test_freq = max(20, fc / 10)
            freqs = np.array([test_freq])
        else:
            # Check gain well above corner frequency
            test_freq = min(fs / 2 - 1, fc * 10)
            freqs = np.array([test_freq])
        response = biquad_response_db(freqs, fs, band)
        assert np.all(np.isfinite(response))
        assert abs(response[0] - gain_db) < 2.0, (
            f"{kind} at Fc={fc}, gain={gain_db}, Fs={fs}: "
            f"expected ~{gain_db} dB at {test_freq} Hz, got {response[0]:.2f} dB"
        )


@pytest.mark.parametrize("fc", FC_VALUES)
@pytest.mark.parametrize("q", Q_VALUES)
@pytest.mark.parametrize("gain_db", GAIN_VALUES)
def test_peaking_response_is_finite_across_grid(fc, q, gain_db):
    """Every combination in the parameter grid produces finite output."""
    fs = 48000
    if fc >= fs / 2:
        pytest.skip("Fc above Nyquist")
    freqs = np.geomspace(20, 20000, 200)
    band = PEQBand("peaking", float(fc), float(gain_db), float(q))
    response = biquad_response_db(freqs, fs, band)
    assert np.all(np.isfinite(response)), f"Non-finite at Fc={fc}, Q={q}, gain={gain_db}"


# ---------------------------------------------------------------------------
# TASK-065: Numerical stability for extreme parameters
# ---------------------------------------------------------------------------

EXTREME_CASES = [
    ("peaking", 10, 96000, 1.0, 6.0, "very low Fc relative to Fs"),
    ("peaking", 23000, 48000, 1.0, 6.0, "near Nyquist"),
    ("peaking", 1000, 48000, 50.0, 6.0, "extremely narrow Q"),
    ("peaking", 1000, 48000, 0.1, 6.0, "extremely wide Q"),
    ("peaking", 1000, 48000, 2.0, 24.0, "very large boost"),
    ("peaking", 1000, 48000, 2.0, -24.0, "very large cut"),
    ("peaking", 10, 96000, 50.0, 12.0, "low Fc + high Q + large gain"),
    ("peaking", 23000, 48000, 30.0, 12.0, "near Nyquist + high Q"),
    ("lowshelf", 20, 96000, 0.7, 18.0, "low shelf at extreme low freq"),
    ("highshelf", 20000, 48000, 0.7, 18.0, "high shelf near Nyquist"),
    ("lowshelf", 10, 44100, 0.7, -18.0, "low shelf deep cut at 10 Hz"),
]


@pytest.mark.parametrize("kind,fc,fs,q,gain_db,desc", EXTREME_CASES)
def test_extreme_parameters_produce_finite_bounded_output(kind, fc, fs, q, gain_db, desc):
    """Extreme parameter combinations must produce finite, bounded results."""
    freqs = np.geomspace(max(5, fc / 10), min(fs / 2 - 1, fc * 10), 200)
    band = PEQBand(kind, float(fc), float(gain_db), float(q))
    response = biquad_response_db(freqs, fs, band)
    assert np.all(np.isfinite(response)), f"Non-finite output for {desc}"
    assert np.all(np.abs(response) < 100), f"Response exceeds ±100 dB for {desc}: max={np.max(np.abs(response)):.1f}"


@pytest.mark.parametrize("kind,fc,fs,q,gain_db,desc", [
    ("peaking", 10, 96000, 1.0, 6.0, "very low Fc"),
    ("peaking", 1000, 48000, 50.0, 6.0, "extreme Q"),
    ("peaking", 1000, 48000, 2.0, 24.0, "large gain"),
])
def test_extreme_peak_gain_within_3db_of_requested(kind, fc, fs, q, gain_db, desc):
    """Even for extreme parameters, peak gain at Fc should be within 3 dB of requested."""
    freqs = np.array([float(fc)])
    band = PEQBand(kind, float(fc), float(gain_db), float(q))
    response = biquad_response_db(freqs, fs, band)
    assert np.all(np.isfinite(response))
    assert abs(response[0] - gain_db) < 3.0, (
        f"{desc}: expected ~{gain_db} dB at Fc={fc}, got {response[0]:.2f} dB"
    )
