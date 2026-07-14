"""Room measurement and modal correction orchestration.

This module provides target curve construction and PEQ fitting for room
measurements with calibrated USB microphones, producing bass-only
corrective EQ (≤ cutoff Hz).
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .analysis import MeasurementResult, analyze_room_measurement
from .app_identity import get_app_identity
from .contracts import (
    ConfidenceSummary,
    FrontendRunSummary,
    RunErrorSummary,
    RunFilterCounts,
    RUN_SUMMARY_SCHEMA_VERSION,
)
from .eq_clipping import assess_eq_clipping
from .exporters import (
    export_camilladsp_filter_snippet_yaml,
    export_camilladsp_filters_yaml,
    export_equalizer_apo_parametric_txt,
)
from .io_utils import save_fr_csv, save_json
from .mic_cal import MicCalibration, calibration_offset
from .exceptions import MeasurementError
from .peq import PEQBand, fit_peq, peq_chain_response_db, FilterBudget
from .pipeline_confidence import summarize_trustworthiness
from .plots import render_fit_graphs
from .signals import SweepSpec
from .targets import TargetCurve, resample_curve


# Constants from TASK-117
ROOM_CUTOFF_DEFAULT_HZ = 300.0
ROOM_MAX_BOOST_DB = 2.0
ROOM_LOW_FREQ_Q_CAP = 12.0

# Adaptive-cutoff bounds (Phase 2): the Schroeder estimate is clamped to a
# sane range so a noisy RT60 or an extreme room volume can't produce a useless
# correction band.
ROOM_CUTOFF_MIN_HZ = 50.0
ROOM_CUTOFF_MAX_HZ = 500.0

# Rough RT60 assumptions (seconds) for the dimensions-only Schroeder estimate.
# A "typical" domestic room lands ~0.5 s; a live/sparse room rings longer, a
# heavily furnished (absorptive) room decays faster. Per Schroeder
# (f = 2000·√(RT60/V)), a longer RT60 raises the modal cutoff.
ROOM_FURNISHING_RT60_S = {
    "sparse": 0.6,
    "typical": 0.5,
    "heavily_furnished": 0.4,
}

# Full-range tilt (Phase 2, opt-in): a gentle house-curve downslope applied
# ABOVE the cutoff. Kept deliberately broad (low Q) and bounded so it shapes
# the through-band as a preference without ever chasing narrow reflections.
ROOM_TILT_Q = 1.0
ROOM_TILT_MAX_GAIN_DB = 6.0
ROOM_TILT_SLOPE_DB_PER_OCT = -0.75


def _validate_room_fit_inputs(
    freqs_hz: np.ndarray,
    values_db: np.ndarray,
    sample_rate: int,
    cutoff_hz: float,
) -> tuple[np.ndarray, np.ndarray, float]:
    freqs = np.asarray(freqs_hz, dtype=np.float64)
    values = np.asarray(values_db, dtype=np.float64)
    if freqs.ndim != 1 or values.ndim != 1 or freqs.shape != values.shape:
        raise MeasurementError("Room fit frequency and response arrays must be 1-D arrays with matching shapes")
    if freqs.size < 2:
        raise MeasurementError("Room fit requires at least two frequency points")
    if np.any(~np.isfinite(freqs)) or np.any(~np.isfinite(values)):
        raise MeasurementError("Room fit inputs contain non-finite values")
    if np.any(freqs <= 0):
        raise MeasurementError("Room fit frequencies must be positive")
    if len(np.unique(freqs)) != len(freqs) or np.any(np.diff(freqs) <= 0):
        raise MeasurementError("Room fit frequencies must be strictly increasing and unique")
    if sample_rate <= 0:
        raise MeasurementError(f"sample_rate must be positive, got {sample_rate}")
    cutoff = float(cutoff_hz)
    if not np.isfinite(cutoff) or cutoff <= 0:
        raise MeasurementError(f"cutoff_hz must be a positive finite value, got {cutoff_hz!r}")
    nyquist_margin = sample_rate / 2.0 - 200.0
    if nyquist_margin <= 0:
        raise MeasurementError(f"sample_rate {sample_rate} is too low for PEQ fitting")
    if cutoff >= nyquist_margin:
        raise MeasurementError(
            f"cutoff_hz {cutoff:.1f} Hz must be below Nyquist safety margin {nyquist_margin:.1f} Hz"
        )
    if not np.any(freqs <= cutoff * 1.1):
        raise MeasurementError("Room fit frequency grid has no points at or below the cutoff")
    return freqs, values, cutoff


def _validate_measurement_grid_pair(left: MeasurementResult, right: MeasurementResult) -> None:
    if left.freqs_hz.shape != right.freqs_hz.shape or not np.allclose(left.freqs_hz, right.freqs_hz):
        raise MeasurementError("Per-channel room recordings produced mismatched frequency grids")


def _room_reference_db(freqs_hz: np.ndarray, values_db: np.ndarray, cutoff_hz: float) -> float:
    """Reference room traces to the transition band around the modal cutoff."""
    low = cutoff_hz * 0.9
    high = cutoff_hz * 1.1
    mask = (freqs_hz >= low) & (freqs_hz <= high)
    if np.any(mask):
        return float(np.median(values_db[mask]))
    return float(np.interp(cutoff_hz, freqs_hz, values_db))


def _reference_room_result_to_cutoff(result: MeasurementResult, cutoff_hz: float) -> MeasurementResult:
    """Remove arbitrary capture/playback gain using the cutoff transition band.

    The shared measurement analyzer normalizes headphone traces at 1 kHz. For
    room correction we only fit the modal band, so use the handoff region around
    the cutoff as the 0 dB reference instead.
    """
    freqs = result.freqs_hz
    left_ref = _room_reference_db(freqs, result.left_db, cutoff_hz)
    right_ref = _room_reference_db(freqs, result.right_db, cutoff_hz)
    left_raw_ref = _room_reference_db(freqs, result.left_raw_db, cutoff_hz)
    right_raw_ref = _room_reference_db(freqs, result.right_raw_db, cutoff_hz)
    diagnostics = dict(result.diagnostics)
    diagnostics["room_reference_hz"] = float(cutoff_hz)
    diagnostics["room_left_reference_db"] = left_ref
    diagnostics["room_right_reference_db"] = right_ref
    return MeasurementResult(
        freqs_hz=freqs,
        left_db=result.left_db - left_ref,
        right_db=result.right_db - right_ref,
        left_raw_db=result.left_raw_db - left_raw_ref,
        right_raw_db=result.right_raw_db - right_raw_ref,
        diagnostics=diagnostics,
    )


def _with_scaled_positive_gains(bands: list[PEQBand], scale: float) -> list[PEQBand]:
    return [
        PEQBand(
            b.kind,
            b.freq,
            b.gain_db * scale if b.gain_db > 0 else b.gain_db,
            b.q,
            slope=b.slope,
        )
        for b in bands
    ]


def _enforce_cumulative_boost_ceiling(
    freqs_hz: np.ndarray,
    sample_rate: int,
    bands: list[PEQBand],
    cutoff_hz: float,
    max_boost_db: float,
) -> list[PEQBand]:
    """Ensure the realized EQ chain never boosts above the room boost ceiling."""
    if max_boost_db < 0 or not any(b.gain_db > 0 for b in bands):
        return bands
    mask = freqs_hz <= cutoff_hz
    if not np.any(mask):
        return bands

    def _peak_boost(scale: float) -> float:
        trial = _with_scaled_positive_gains(bands, scale)
        response = peq_chain_response_db(freqs_hz, sample_rate, trial)
        return float(np.max(response[mask]))

    if _peak_boost(1.0) <= max_boost_db + 1e-6:
        return bands

    lo, hi = 0.0, 1.0
    for _ in range(32):
        mid = (lo + hi) / 2.0
        if _peak_boost(mid) <= max_boost_db + 1e-6:
            lo = mid
        else:
            hi = mid
    return _with_scaled_positive_gains(bands, lo)


@dataclass
class RoomFitResult:
    """Result of room measurement fitting.
    
    Attributes:
        result: MeasurementResult with room frequency response
        eq_bands: PEQ bands for correction
        target: Target curve used
        fit_report: Detailed fitting report
        run_summary: FrontendRunSummary dict
        out_dir: Output directory path
        warnings: List of warning messages
    """
    result: MeasurementResult
    eq_bands: list[PEQBand]
    target: TargetCurve
    fit_report: dict[str, Any]
    run_summary: dict[str, Any]
    out_dir: Path
    warnings: list[str]
    # Per-speaker stereo (Phase 2): populated when recording_left/recording_right
    # are used; otherwise both mirror the mono `eq_bands`.
    eq_bands_left: list[PEQBand] | None = None
    eq_bands_right: list[PEQBand] | None = None


def build_room_target(
    freqs_hz: np.ndarray,
    sub_bass_rolloff: bool = True,
) -> TargetCurve:
    """Build a flat room target curve through the modal band.
    
    Returns a flat (0 dB) curve with optional ~2-3 dB rolloff below ~40 Hz
    to account for typical room measurement floor noise and mic limitations.
    
    Args:
        freqs_hz: Frequency grid for the target
        sub_bass_rolloff: If True, apply gentle rolloff below 40 Hz
        
    Returns:
        TargetCurve with room-appropriate target values
    """
    values_db = np.zeros_like(freqs_hz, dtype=np.float64)
    
    if sub_bass_rolloff:
        # Apply ~2-3 dB rolloff below 40 Hz using gentle slope
        # At 20 Hz: ~-2.5 dB, at 40 Hz: 0 dB, linear interpolation in log domain
        rolloff_freqs = freqs_hz <= 40.0
        if np.any(rolloff_freqs):
            # Simple linear rolloff: -2.5 dB at 20 Hz, 0 dB at 40 Hz
            rolloff_db = -2.5 * (1.0 - np.interp(
                freqs_hz[rolloff_freqs], [20.0, 40.0], [0.0, 1.0]
            ))
            values_db[rolloff_freqs] = rolloff_db
    
    return TargetCurve(freqs_hz, values_db, name='room_modal_flat', semantics='absolute')


def fit_room_bands(
    freqs_hz: np.ndarray,
    eq_target_db: np.ndarray,
    sample_rate: int,
    cutoff_hz: float | str,
    max_boost_db: float = ROOM_MAX_BOOST_DB,
    low_freq_q_cap: float = ROOM_LOW_FREQ_Q_CAP,
    *,
    impulse_response: np.ndarray | None = None,
    room_volume_m3: float | None = None,
    enable_tilt: bool = False,
) -> list[PEQBand]:
    """Fit PEQ bands for room correction with band-limiting and boost constraints.

    Pure core function that wraps fit_peq with room-specific constraints:
    - Band-limit: no filter above cutoff_hz (structural: data filtered before fitting)
    - Boost ceiling: max_boost_db enforced structurally
    - Narrow mode support: Q cap for sub-100 Hz

    Args:
        freqs_hz: Frequency grid in Hz
        eq_target_db: EQ target (desired response) in dB
        sample_rate: Sample rate
        cutoff_hz: Maximum frequency for fitted bands, or ``'auto'`` to derive an
            RT60-based Schroeder cutoff from ``impulse_response``/``room_volume_m3``.
        max_boost_db: Maximum allowed boost (positive gain)
        low_freq_q_cap: Maximum Q for low frequencies (< 120 Hz)
        impulse_response: Optional room impulse response, used only for ``cutoff_hz='auto'``.
        room_volume_m3: Optional room volume in m³, used only for ``cutoff_hz='auto'``.
        enable_tilt: When True, append an opt-in gentle house-curve tilt above the
            cutoff (see :func:`fit_full_range_tilt`).

    Returns:
        List of fitted PEQ bands (modal bands ≤ cutoff, plus optional tilt bands above).
    """
    if isinstance(cutoff_hz, str):
        if cutoff_hz != 'auto':
            raise MeasurementError(f"cutoff_hz must be a number or 'auto', got {cutoff_hz!r}")
        cutoff_hz = estimate_schroeder_cutoff(
            impulse_response,
            sample_rate,
            room_volume_m3 if room_volume_m3 is not None else 50.0,
        )
    freqs_hz, eq_target_db, cutoff_hz = _validate_room_fit_inputs(
        freqs_hz, eq_target_db, sample_rate, cutoff_hz
    )
    if not np.isfinite(max_boost_db) or max_boost_db < 0:
        raise MeasurementError(f"max_boost_db must be a non-negative finite value, got {max_boost_db!r}")
    if not np.isfinite(low_freq_q_cap) or low_freq_q_cap <= 0:
        raise MeasurementError(f"low_freq_q_cap must be a positive finite value, got {low_freq_q_cap!r}")

    # Structural cutoff: filter data ABOVE cutoff Hz before fitting.
    # This ensures the residual/error signal does not see above-cutoff frequencies.
    mask = freqs_hz <= cutoff_hz * 1.1  # Include small margin (10% above) for edge effects
    fit_freqs_hz = freqs_hz[mask]
    fit_eq_target_db = eq_target_db[mask]

    bands = fit_peq(
        fit_freqs_hz,
        fit_eq_target_db,
        sample_rate,
        max_filters=8,
        max_gain_db=12.0,  # Max cut depth
        max_q=12.0,
        max_freq_hz=cutoff_hz,
        low_freq_q_cap=low_freq_q_cap,
        max_boost_db=max_boost_db,
    )

    if enable_tilt:
        bands = bands + fit_full_range_tilt(
            freqs_hz, eq_target_db, cutoff_hz, enable_tilt=True
        )
    bands = _enforce_cumulative_boost_ceiling(
        freqs_hz,
        sample_rate,
        bands,
        cutoff_hz,
        max_boost_db,
    )
    return bands


def _estimate_rt60(impulse_response: np.ndarray, sample_rate: int) -> float | None:
    """Estimate RT60 (s) from an impulse response via Schroeder backward integration.

    Uses a T20 fit (energy decay curve from −5 dB to −25 dB, extrapolated to 60 dB).
    Returns ``None`` when the IR is too short or too noisy to yield a decay slope.
    """
    ir = np.asarray(impulse_response, dtype=np.float64).ravel()
    # Need a meaningful decay window; a handful of samples cannot yield RT60.
    if ir.size < int(0.05 * sample_rate):
        return None

    energy = ir ** 2
    # Schroeder energy decay curve: reverse cumulative integral of the energy.
    edc = np.cumsum(energy[::-1])[::-1]
    if edc[0] <= 0:
        return None
    edc_db = 10.0 * np.log10(edc / edc[0] + 1e-20)

    below_5 = np.where(edc_db <= -5.0)[0]
    below_25 = np.where(edc_db <= -25.0)[0]
    if below_5.size == 0 or below_25.size == 0:
        return None
    i_start = int(below_5[0])
    i_end = int(below_25[0])
    if i_end <= i_start:
        return None

    t = np.arange(i_start, i_end + 1) / float(sample_rate)
    slope = float(np.polyfit(t, edc_db[i_start:i_end + 1], 1)[0])  # dB/s (negative)
    if slope >= 0:
        return None
    rt60 = -60.0 / slope
    if not np.isfinite(rt60) or rt60 <= 0:
        return None
    return rt60


def estimate_schroeder_cutoff(
    impulse_response: np.ndarray | None,
    sample_rate: int,
    room_volume_m3: float,
) -> float:
    """Estimate the modal cutoff from RT60 and room volume via the Schroeder formula.

    ``f_schroeder ≈ 2000 · √(RT60 / V)``. RT60 is derived from the impulse response
    (Schroeder backward integration). When the IR is unavailable or too short/noisy
    to yield RT60, falls back to :data:`ROOM_CUTOFF_DEFAULT_HZ`. The result is clamped
    to [:data:`ROOM_CUTOFF_MIN_HZ`, :data:`ROOM_CUTOFF_MAX_HZ`].
    """
    if impulse_response is None or room_volume_m3 <= 0:
        return ROOM_CUTOFF_DEFAULT_HZ

    rt60 = _estimate_rt60(impulse_response, sample_rate)
    if rt60 is None:
        return ROOM_CUTOFF_DEFAULT_HZ

    cutoff = 2000.0 * np.sqrt(rt60 / room_volume_m3)
    return float(np.clip(cutoff, ROOM_CUTOFF_MIN_HZ, ROOM_CUTOFF_MAX_HZ))


def estimate_cutoff_from_dimensions(
    length_m: float,
    width_m: float,
    height_m: float,
    furnishing: str = "typical",
    return_metadata: bool = False,
) -> float | dict[str, Any]:
    """Rough modal cutoff from room dimensions, without a measured RT60.

    Computes volume from L×W×H and assumes an RT60 by furnishing level, then applies
    the Schroeder formula ``f = 2000·√(RT60/V)``. A live/sparse room rings longer
    (higher RT60 → higher cutoff); a heavily furnished, absorptive room decays faster
    (lower RT60 → lower cutoff). The result is clamped to the adaptive-cutoff range.

    Args:
        length_m, width_m, height_m: Room dimensions in metres (0.1–100 each).
        furnishing: One of ``'sparse'``, ``'typical'`` (default), ``'heavily_furnished'``.
        return_metadata: When True, return a dict with the cutoff and the inputs used.

    Raises:
        ValueError: on non-positive, implausibly small (<0.1 m), or large (>100 m)
            dimensions, or an unknown furnishing level.
    """
    for name, value in (("length_m", length_m), ("width_m", width_m), ("height_m", height_m)):
        if value <= 0:
            raise MeasurementError(f"{name} must be positive, got {value}")
        if value < 0.1:
            raise MeasurementError(f"{name}={value} m is implausibly small (min 0.1 m)")
        if value > 100.0:
            raise MeasurementError(f"{name}={value} m is implausibly large (max 100 m)")

    if furnishing not in ROOM_FURNISHING_RT60_S:
        raise MeasurementError(
            f"furnishing must be one of {sorted(ROOM_FURNISHING_RT60_S)}, got {furnishing!r}"
        )

    volume_m3 = length_m * width_m * height_m
    rt60_s = ROOM_FURNISHING_RT60_S[furnishing]
    cutoff = float(
        np.clip(2000.0 * np.sqrt(rt60_s / volume_m3), ROOM_CUTOFF_MIN_HZ, ROOM_CUTOFF_MAX_HZ)
    )

    if return_metadata:
        return {
            "cutoff_hz": cutoff,
            "volume_m3": volume_m3,
            "rt60_s": rt60_s,
            "furnishing": furnishing,
        }
    return cutoff


def fit_full_range_tilt(
    freqs_hz: np.ndarray,
    measured_db: np.ndarray,
    cutoff_hz: float,
    enable_tilt: bool = False,
) -> list[PEQBand]:
    """Opt-in gentle house-curve tilt applied ABOVE the cutoff.

    Emits a small set of deliberately broad, low-Q peaking bands that impose a gentle
    downward slope above the modal cutoff (a listener-preference tilt), leaving the
    below-cutoff modal correction to the main fitter. Guardrails, by construction:

    - only bands with centre frequency > ``cutoff_hz`` are produced,
    - Q is fixed low (:data:`ROOM_TILT_Q` ≤ 2) so nothing chases narrow reflections,
    - gain is bounded to ±:data:`ROOM_TILT_MAX_GAIN_DB`.

    Returns an empty list when ``enable_tilt`` is False. ``measured_db`` is accepted for
    signature symmetry with the modal fitter and future measurement-aware shaping; the
    MVP tilt is a fixed preference slope and does not fit measured features.
    """
    if not enable_tilt:
        return []

    freqs = np.asarray(freqs_hz, dtype=np.float64)
    measured = np.asarray(measured_db, dtype=np.float64)
    if freqs.ndim != 1 or measured.ndim != 1 or freqs.shape != measured.shape:
        raise MeasurementError("Tilt frequency and response arrays must be 1-D arrays with matching shapes")
    if freqs.size == 0:
        return []
    if np.any(~np.isfinite(freqs)) or np.any(~np.isfinite(measured)) or np.any(freqs <= 0):
        raise MeasurementError("Tilt inputs contain invalid frequency/response values")
    if len(np.unique(freqs)) != len(freqs) or np.any(np.diff(freqs) <= 0):
        raise MeasurementError("Tilt frequencies must be strictly increasing and unique")
    if not np.isfinite(cutoff_hz) or cutoff_hz <= 0:
        raise MeasurementError(f"cutoff_hz must be a positive finite value, got {cutoff_hz!r}")
    nyquist = float(freqs[-1])

    bands: list[PEQBand] = []
    # Place one broad band per octave above the cutoff, implementing a gentle
    # downward slope referenced to 0 dB at the cutoff. Octave centres start one
    # octave above the cutoff, so no band lands on a specific feature frequency.
    fc = cutoff_hz * 2.0
    while fc < nyquist:
        gain = ROOM_TILT_SLOPE_DB_PER_OCT * np.log2(fc / cutoff_hz)
        gain = float(np.clip(gain, -ROOM_TILT_MAX_GAIN_DB, ROOM_TILT_MAX_GAIN_DB))
        if abs(gain) >= 0.1:  # skip negligible bands
            bands.append(PEQBand("peaking", float(fc), gain, ROOM_TILT_Q))
        fc *= 2.0
    return bands


def _energy_average_responses(
    result1: MeasurementResult,
    result2: MeasurementResult,
) -> MeasurementResult:
    """Energy-average two room measurement responses (magnitude-domain average).
    
    Converts dB to linear magnitude, averages, converts back to dB.
    """
    # Convert dB to linear magnitude (power = 10^(db/10))
    left1_mag = 10 ** (result1.left_db / 10.0)
    left2_mag = 10 ** (result2.left_db / 10.0)
    right1_mag = 10 ** (result1.right_db / 10.0)
    right2_mag = 10 ** (result2.right_db / 10.0)
    
    left_raw1_mag = 10 ** (result1.left_raw_db / 10.0)
    left_raw2_mag = 10 ** (result2.left_raw_db / 10.0)
    right_raw1_mag = 10 ** (result1.right_raw_db / 10.0)
    right_raw2_mag = 10 ** (result2.right_raw_db / 10.0)
    
    # Energy (power) average: arithmetic mean of the linear power values
    # (10^(dB/10)), converted back to dB below.
    left_avg = 0.5 * (left1_mag + left2_mag)
    right_avg = 0.5 * (right1_mag + right2_mag)
    left_raw_avg = 0.5 * (left_raw1_mag + left_raw2_mag)
    right_raw_avg = 0.5 * (right_raw1_mag + right_raw2_mag)
    
    # Convert back to dB
    left_db = 10 * np.log10(left_avg + 1e-12)
    right_db = 10 * np.log10(right_avg + 1e-12)
    left_raw_db = 10 * np.log10(left_raw_avg + 1e-12)
    right_raw_db = 10 * np.log10(right_raw_avg + 1e-12)
    
    # Merge diagnostics: use result1 but flag that this is averaged
    diagnostics = dict(result1.diagnostics)
    diagnostics['two_position_averaged'] = True

    return MeasurementResult(
        freqs_hz=result1.freqs_hz.copy(),
        left_db=left_db,
        right_db=right_db,
        left_raw_db=left_raw_db,
        right_raw_db=right_raw_db,
        diagnostics=diagnostics,
    )


def energy_average_responses_n(results: list[MeasurementResult]) -> MeasurementResult:
    """Energy-average N room measurements (moving-microphone / multi-point method).

    Generalizes :func:`_energy_average_responses` to N positions: each channel is
    converted from dB to linear power (10^(dB/10)), averaged across positions, and
    converted back to dB. A single position is returned unchanged. The result's
    diagnostics carry ``n_position_averaged`` = N.

    Raises:
        ValueError: if the list is empty or the frequency grids differ.
    """
    if not results:
        raise MeasurementError("energy_average_responses_n requires a non-empty list of results")

    reference_freqs = results[0].freqs_hz
    for other in results[1:]:
        if other.freqs_hz.shape != reference_freqs.shape or not np.allclose(
            other.freqs_hz, reference_freqs
        ):
            raise MeasurementError(
                "Cannot average measurements with mismatched frequency grids"
            )

    if len(results) == 1:
        only = results[0]
        diagnostics = dict(only.diagnostics)
        diagnostics['n_position_averaged'] = 1
        return MeasurementResult(
            freqs_hz=only.freqs_hz.copy(),
            left_db=only.left_db.copy(),
            right_db=only.right_db.copy(),
            left_raw_db=only.left_raw_db.copy(),
            right_raw_db=only.right_raw_db.copy(),
            diagnostics=diagnostics,
        )

    def _avg(attr: str) -> np.ndarray:
        power = np.mean([10 ** (getattr(r, attr) / 10.0) for r in results], axis=0)
        return 10 * np.log10(power + 1e-12)  # type: ignore[no-any-return]

    diagnostics = dict(results[0].diagnostics)
    diagnostics['n_position_averaged'] = len(results)
    if len(results) == 2:
        # Keep the existing two-position flag so downstream single-point checks
        # continue to treat a 2-position average the same way.
        diagnostics['two_position_averaged'] = True

    return MeasurementResult(
        freqs_hz=reference_freqs.copy(),
        left_db=_avg('left_db'),
        right_db=_avg('right_db'),
        left_raw_db=_avg('left_raw_db'),
        right_raw_db=_avg('right_raw_db'),
        diagnostics=diagnostics,
    )


def _assess_room_fit_quality(result: MeasurementResult) -> list[str]:
    """Generate measurement-quality warnings for a room fit."""
    warnings = []

    # Check for single-point measurement caveats
    averaged_positions = int(result.diagnostics.get('n_position_averaged', 1))
    if averaged_positions <= 1 and not result.diagnostics.get('two_position_averaged', False):
        warnings.append(
            "Single-point room measurement. Modal response varies with position. "
            "Consider averaging measurements from two or more listening positions."
        )

    # Check for sub-cutoff issues
    min_freq = float(np.min(result.freqs_hz))
    if min_freq > 30.0:
        warnings.append(
            f"Low-frequency measurement starts at {min_freq:.1f} Hz. "
            "Room mode resolution below this frequency is limited."
        )

    return warnings


def _write_room_results_guide(
    out_dir: Path,
    trust_summary: ConfidenceSummary | None,
    warnings: list[str],
) -> Path:
    """Write human-readable README.txt for room fit results."""
    content = ['headmatch room measurement results', '=' * 40, '']
    content.append('This folder contains the room measurement and EQ correction files.')
    content.append('')
    content.append('Files')
    content.append('-----')
    for name, desc in [
        ('room_fr.csv', 'Measured room frequency response (calibrated, averaged if two positions).'),
        ('target_curve.csv', 'The target curve used for fitting (flat through modal band).'),
        ('equalizer_apo.txt', 'Equalizer APO parametric preset for room correction.'),
        ('camilladsp_full.yaml', 'Full CamillaDSP config template.'),
        ('camilladsp_filters_only.yaml', 'Filters-only snippet for existing config.'),
        ('fit_overview.svg', 'Room fit graph with cutoff marker.'),
        ('run_summary.json', 'Machine-readable summary of the run.'),
        ('fit_report.json', 'Detailed PEQ band list and diagnostics.'),
        ('README.txt', 'This file.'),
    ]:
        content.append(f'- {name}: {desc}')
    
    content.append('')
    content.append('Room-specific notes')
    content.append('-------------------')
    
    if warnings:
        content.append('Warnings:')
        for w in warnings:
            content.append(f'  - {w}')
    else:
        content.append('No warnings.')
    
    if trust_summary:
        content.append('')
        content.append('Trust Summary:')
        content.append(f"  Confidence: {trust_summary.label} ({trust_summary.score}/100)")
        content.append(f"  Headline: {trust_summary.headline}")
    
    content.append('')
    content.append('Usage')
    content.append('-----')
    content.append('Load equalizer_apo.txt into Equalizer APO or')
    content.append('use the CamillaDSP YAML files with your DSP setup.')
    content.append('')
    content.append('Note: This correction is only valid through the fitted cutoff frequency.')
    
    path = out_dir / 'README.txt'
    path.write_text('\n'.join(content) + '\n', encoding='utf-8')
    return path


def run_room_fit(
    recording: str | Path | None = None,
    recording_two: str | Path | None = None,
    mic_cal: MicCalibration | None = None,
    cutoff_hz: float = ROOM_CUTOFF_DEFAULT_HZ,
    max_boost_db: float = ROOM_MAX_BOOST_DB,
    target_csv: str | Path | None = None,
    out_dir: str | Path | None = None,
    sweep_spec: SweepSpec | None = None,
    *,
    additional_recordings: list[str | Path] | None = None,
    mmm_sweep: str | Path | None = None,
    recording_left: str | Path | None = None,
    recording_right: str | Path | None = None,
    enable_tilt: bool = False,
) -> RoomFitResult:
    """Run full room measurement fitting workflow.

    Orchestrates the room measurement analysis, target building,
    PEQ fitting, and artifact generation.

    Args:
        recording: Path to primary room measurement WAV file (mono correction path).
        recording_two: Optional second position measurement, energy-averaged with the first.
        mic_cal: Optional microphone calibration (applies calibration_offset)
        cutoff_hz: Maximum frequency for EQ correction
        max_boost_db: Maximum allowed boost (typically ROOM_MAX_BOOST_DB=2.0)
        target_csv: Optional custom target CSV path (uses flat target if None)
        out_dir: Output directory for results
        sweep_spec: Sweep specification the recording was made with. Must match
            the sweep used at capture time (sample rate, duration, band); the
            reference sweep is regenerated from it for deconvolution/alignment.
        additional_recordings: Extra position recordings for N-position (MMM) energy
            averaging, combined with ``recording``/``recording_two``.
        mmm_sweep: Optional continuous moving-microphone capture, treated as one more
            position in the energy average.
        recording_left, recording_right: Per-speaker stereo path. When both are given,
            each channel is analyzed and fit independently, producing separate L/R EQ.
        enable_tilt: Opt-in gentle house-curve tilt above the cutoff (see fit_full_range_tilt).

    Returns:
        RoomFitResult with all outputs and metadata
    """
    if out_dir is None:
        raise MeasurementError("run_room_fit requires out_dir")
    if sweep_spec is None:
        raise MeasurementError("run_room_fit requires sweep_spec")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    fit_warnings: list[str] = []

    # Validate mic_cal - warn if missing
    if mic_cal is None:
        warnings.warn(
            "No microphone calibration provided. Measurement may be inaccurate. "
            "Consider using a calibration file for best results.",
            UserWarning
        )
        fit_warnings.append(
            "No microphone calibration: measurement accuracy is unverified."
        )

    # Analyze room measurement(s) using the caller's sweep spec so the
    # regenerated reference matches how the recording was actually captured.
    sample_rate = sweep_spec.sample_rate

    def _measure(path: str | Path) -> MeasurementResult:
        res = analyze_room_measurement(path, sweep_spec, out_dir=None)
        if mic_cal is None:
            return res
        offset_db = calibration_offset(mic_cal, res.freqs_hz)
        return MeasurementResult(
            freqs_hz=res.freqs_hz,
            left_db=res.left_db - offset_db,
            right_db=res.right_db - offset_db,
            left_raw_db=res.left_raw_db - offset_db,
            right_raw_db=res.right_raw_db - offset_db,
            diagnostics=res.diagnostics,
        )

    per_channel = recording_left is not None and recording_right is not None
    if per_channel:
        if recording is not None:
            raise MeasurementError(
                "Provide either 'recording' (mono) or recording_left+recording_right "
                "(per-speaker), not both."
            )
        res_l = _measure(recording_left)  # type: ignore[arg-type]
        res_r = _measure(recording_right)  # type: ignore[arg-type]
        _validate_measurement_grid_pair(res_l, res_r)
        diagnostics = dict(res_l.diagnostics)
        diagnostics['per_channel'] = True
        # Combined result carries the real L/R responses for graphs/report.
        result = MeasurementResult(
            freqs_hz=res_l.freqs_hz,
            left_db=res_l.left_db,
            right_db=res_r.left_db,
            left_raw_db=res_l.left_raw_db,
            right_raw_db=res_r.left_raw_db,
            diagnostics=diagnostics,
        )
        n_positions = 1
        single_point = True
    else:
        if recording is None:
            raise MeasurementError(
                "run_room_fit requires 'recording' (or recording_left+recording_right)"
            )
        recordings: list[str | Path] = [recording]
        if recording_two is not None:
            recordings.append(recording_two)
        if additional_recordings:
            recordings.extend(additional_recordings)
        if mmm_sweep is not None:
            recordings.append(mmm_sweep)
        results = [_measure(r) for r in recordings]
        result = energy_average_responses_n(results) if len(results) > 1 else results[0]
        n_positions = len(recordings)
        single_point = n_positions == 1

    result = _reference_room_result_to_cutoff(result, cutoff_hz)
    measured_left_db = result.left_db
    measured_right_db = result.right_db

    # Build or load target. Room targets are bass-only (≤ cutoff), so load
    # user CSVs without the 1 kHz normalization that headphone targets require.
    if target_csv is not None:
        from .targets import load_curve
        target = load_curve(target_csv, normalize=False)
        target = resample_curve(target, result.freqs_hz)
    else:
        target = build_room_target(result.freqs_hz, sub_bass_rolloff=True)

    # Anchor the target to 0 dB at the cutoff — the handoff to the uncorrected
    # band above it. A room target describes how much to lift/shape the bass
    # *relative to the through-band*, so referencing every target to its own
    # value at the cutoff makes the CSV author's choice of absolute 0 dB
    # reference irrelevant and keeps the handoff identical to the flat target
    # (no arbitrary offset or dip at the crossover). The default flat target is
    # already 0 dB at the cutoff, so this is a no-op there.
    anchor_db = float(np.interp(cutoff_hz, target.freqs_hz, target.values_db))
    if anchor_db != 0.0:
        target = TargetCurve(
            freqs_hz=target.freqs_hz,
            values_db=target.values_db - anchor_db,
            name=target.name,
            semantics=target.semantics,
        )

    def _desired_and_eq_target(measured_db: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        # Desired in-room response, honoring the target's semantics (must match how
        # render_fit_graphs interprets the same target). A 'relative' target holds
        # deltas about the measurement; an 'absolute' target is the response itself.
        if target.semantics == 'relative':
            desired = measured_db + target.values_db
        else:
            desired = target.values_db
        # For room: measured + eq = desired => eq_target = desired - measured
        return desired, desired - measured_db

    def _fit(measured_db: np.ndarray) -> list[PEQBand]:
        _, eq_target_db = _desired_and_eq_target(measured_db)
        return fit_room_bands(
            result.freqs_hz,
            eq_target_db,
            sample_rate,
            cutoff_hz=cutoff_hz,
            max_boost_db=max_boost_db,
            low_freq_q_cap=ROOM_LOW_FREQ_Q_CAP,
            enable_tilt=enable_tilt,
        )

    desired_left_db, _ = _desired_and_eq_target(measured_left_db)
    if per_channel:
        desired_right_db, _ = _desired_and_eq_target(measured_right_db)
        eq_bands_left = _fit(measured_left_db)
        eq_bands_right = _fit(measured_right_db)
    else:
        desired_right_db = desired_left_db
        eq_bands_left = _fit(measured_left_db)
        eq_bands_right = eq_bands_left

    # Legacy single-list field mirrors the left channel (identical to right in mono).
    eq_bands = eq_bands_left

    # Assess fit quality and generate warnings
    fit_warnings.extend(_assess_room_fit_quality(result))

    # Compute predicted error per channel against the desired response.
    # Bands are limited to ≤ cutoff, so error is measured only within the
    # corrected band (higher frequencies would inflate it with uncorrected deviation).
    fit_mask = result.freqs_hz <= cutoff_hz

    def _predicted_error(measured_db: np.ndarray, desired_db: np.ndarray, bands: list[PEQBand]) -> tuple[float, float]:
        residual = measured_db + peq_chain_response_db(result.freqs_hz, sample_rate, bands) - desired_db
        if np.any(fit_mask):
            return (
                float(np.sqrt(np.mean(residual[fit_mask] ** 2))),
                float(np.max(np.abs(residual[fit_mask]))),
            )
        return 0.0, 0.0

    predicted_left_rms, predicted_left_max = _predicted_error(measured_left_db, desired_left_db, eq_bands_left)
    predicted_right_rms, predicted_right_max = _predicted_error(measured_right_db, desired_right_db, eq_bands_right)

    # Build report
    fit_report: dict[str, Any] = {
        'peq_bands_left': [
            {'kind': b.kind, 'freq': b.freq, 'gain_db': b.gain_db, 'q': b.q}
            for b in eq_bands_left
        ],
        'peq_bands_right': [
            {'kind': b.kind, 'freq': b.freq, 'gain_db': b.gain_db, 'q': b.q}
            for b in eq_bands_right
        ],
        'predicted_left_rms_error_db': predicted_left_rms,
        'predicted_right_rms_error_db': predicted_right_rms,
        'predicted_left_max_error_db': predicted_left_max,
        'predicted_right_max_error_db': predicted_right_max,
        'cutoff_hz': cutoff_hz,
        'max_boost_db': max_boost_db,
        'low_freq_q_cap': ROOM_LOW_FREQ_Q_CAP,
        'qualitative': 'acceptable' if (max(predicted_left_rms, predicted_right_rms) < 3.0) else 'marginal',
        'single_point': single_point,
        'n_positions': n_positions,
        'per_channel': per_channel,
        'tilt_enabled': enable_tilt,
    }

    # EQ clipping assessment
    clipping = assess_eq_clipping(result.freqs_hz, sample_rate, eq_bands_left, eq_bands_right)
    fit_report['eq_clipping_assessment'] = {
        'will_clip': clipping.will_clip,
        'preamp_db': clipping.total_preamp_db,
        'headroom_loss_db': clipping.headroom_loss_db,
        'quality_concern': clipping.quality_concern,
    }

    # Export EQ presets
    export_equalizer_apo_parametric_txt(
        out_dir / 'equalizer_apo.txt',
        eq_bands_left,
        eq_bands_right,
        preamp_db=clipping.total_preamp_db if clipping.will_clip else None,
    )
    export_camilladsp_filters_yaml(out_dir / 'camilladsp_full.yaml', eq_bands_left, eq_bands_right, samplerate=sample_rate)
    export_camilladsp_filter_snippet_yaml(out_dir / 'camilladsp_filters_only.yaml', eq_bands_left, eq_bands_right)

    # Export room FR CSV
    save_fr_csv(out_dir / 'room_fr.csv', result.freqs_hz, result.left_db, column_name='response_db')

    # Export target curve
    save_fr_csv(out_dir / 'target_curve.csv', target.freqs_hz, target.values_db, column_name='target_db')

    # Render graphs with cutoff marker
    render_fit_graphs(
        out_dir, result, target, sample_rate, eq_bands_left, eq_bands_right, cutoff_hz=cutoff_hz
    )

    # Trustworthiness assessment
    trust_summary = summarize_trustworthiness(result, fit_report, workflow='room')

    # Build run summary
    identity = get_app_identity()
    summary = FrontendRunSummary(
        schema_version=RUN_SUMMARY_SCHEMA_VERSION,
        kind='room',
        out_dir=str(out_dir),
        sample_rate=sample_rate,
        frequency_points=len(result.freqs_hz),
        target=target.name,
        filters=RunFilterCounts(left=len(eq_bands_left), right=len(eq_bands_right)),
        predicted_error_db=RunErrorSummary(
            left_rms=predicted_left_rms,
            right_rms=predicted_right_rms,
            left_max=predicted_left_max,
            right_max=predicted_right_max,
        ),
        confidence=trust_summary,
        plots={
            'overview': str(out_dir / 'fit_overview.svg'),
            'left': str(out_dir / 'fit_left.svg'),
            'right': str(out_dir / 'fit_right.svg'),
        },
        results_guide=str(out_dir / 'README.txt'),
        filter_budget=FilterBudget(family='peq', max_filters=8),
        eq_clipping_assessment=fit_report['eq_clipping_assessment'],
        generated_by=identity.as_metadata(),
        cutoff_hz=cutoff_hz,
        mic_cal_applied=mic_cal is not None,
        single_point=single_point,
    )

    # Write JSON artifacts
    save_json(out_dir / 'run_summary.json', summary.to_dict())
    save_json(out_dir / 'fit_report.json', fit_report)

    # Write README
    _write_room_results_guide(out_dir, trust_summary, fit_warnings)

    return RoomFitResult(
        result=result,
        eq_bands=eq_bands,
        target=target,
        fit_report=fit_report,
        run_summary=summary.to_dict(),
        out_dir=out_dir,
        warnings=fit_warnings,
        eq_bands_left=eq_bands_left,
        eq_bands_right=eq_bands_right,
    )


def prepare_room_measurement(
    spec: SweepSpec,
    mic_cal: MicCalibration | None,
    cutoff_hz: float,
    max_boost_db: float,
    listen_position_two: bool,
    out_dir: Path,
) -> dict:
    """Prepare offline measurement package for room correction.

    Generates a sweep WAV and metadata JSON for manual room measurement.
    The generated package can be played through speakers and recorded
    at the listening position(s).

    Args:
        spec: Sweep specification for the measurement signal
        mic_cal: Optional microphone calibration for field measurements
        cutoff_hz: Maximum frequency for EQ correction
        max_boost_db: Maximum allowed boost
        listen_position_two: If True, prepare for two-position measurement
        out_dir: Directory to write output files

    Returns:
        Dictionary with file paths and configuration
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    from .measure import render_sweep_file, save_json
    from .app_identity import get_app_identity

    sweep_wav = out_dir / "room_sweep.wav"
    metadata_json = out_dir / "room_measurement.json"

    render_sweep_file(spec, sweep_wav)

    identity = get_app_identity()

    mic_cal_path = mic_cal.source if mic_cal else None

    metadata = {
        "generated_by": identity.as_metadata(),
        "mode": "room_offline",
        "recommended_recorder": "UMIK-1 with USB interface",
        "mic_calibration": {
            "applied": mic_cal is not None,
            "source_file": str(mic_cal_path) if mic_cal_path else None,
        },
        "measurement_config": {
            "cutoff_hz": cutoff_hz,
            "max_boost_db": max_boost_db,
            "single_point": not listen_position_two,
        },
        "sweep": {
            "sample_rate": spec.sample_rate,
            "duration_s": spec.duration_s,
            "f_start": spec.f_start,
            "f_end": spec.f_end,
            "pre_silence_s": spec.pre_silence_s,
            "post_silence_s": spec.post_silence_s,
            "amplitude": spec.amplitude,
        },
        "instructions": [
            "Connect the measurement microphone to a USB audio interface.",
            "Position the microphone at the primary listening position (ear height).",
            "Disable auto gain, limiter, low cut, and any other processing.",
            "Ensure the room is quiet during measurement.",
            *([
                "Record sweep at position 1, then move mic and repeat for position 2."
            ] if listen_position_two else [
                "Record the sweep from primary listening position only."
            ]),
        ],
        "files": {
            "sweep_wav": str(sweep_wav),
        },
    }

    save_json(metadata_json, metadata)

    return {
        "sweep_wav": sweep_wav,
        "metadata_json": metadata_json,
        "config": metadata["measurement_config"],
    }
