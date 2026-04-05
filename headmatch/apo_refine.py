"""Refine an imported APO preset against a measurement.

Takes existing PEQ bands (from an APO import) and re-optimises them
against a measurement + target using joint Nelder-Mead refinement.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

import numpy as np

from .analysis import MeasurementResult, analyze_measurement
from .apo_import import load_apo_preset
from .peq import (
    FitObjective,
    FilterBudget,
    PEQBand,
    _refine_bands_jointly,
    peq_chain_response_db,
)
from .pipeline import _resolve_target_curves, _metrics
from .pipeline_artifacts import write_fit_artifacts
from .pipeline_confidence import summarize_trustworthiness
from .signals import SweepSpec
from .targets import TargetCurve, create_flat_target, load_curve, resample_curve
from .app_identity import get_app_identity
from .io_utils import save_json


def refine_apo_preset(
    preset_path: str | Path,
    recording_wav: str | Path,
    sweep_spec: SweepSpec,
    out_dir: str | Path,
    target_path: str | Path | None = None,
    max_gain_db: float = 8.0,
    max_q: float = 4.5,
) -> dict:
    """Load an APO preset, refine against a measurement, and write full artifacts.

    Returns the fit report dict (same structure as fit_from_measurement).
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load preset
    left_bands_orig, right_bands_orig = load_apo_preset(preset_path)

    # Analyze measurement
    result = analyze_measurement(recording_wav, sweep_spec, out_dir=out_dir)

    # Resolve target
    target = load_curve(target_path) if target_path else create_flat_target(result.freqs_hz)
    resolved = _resolve_target_curves(result, target)

    # Refine each channel
    left_bands = _refine_channel(
        result.freqs_hz, result.left_db, resolved.left_values_db,
        left_bands_orig, result.sample_rate if hasattr(result, 'sample_rate') else sweep_spec.sample_rate,
        max_gain_db, max_q,
    )
    right_bands = _refine_channel(
        result.freqs_hz, result.right_db, resolved.right_values_db,
        right_bands_orig, sweep_spec.sample_rate,
        max_gain_db, max_q,
    )

    # Compute metrics
    sample_rate = sweep_spec.sample_rate
    left_pred = result.left_db + peq_chain_response_db(result.freqs_hz, sample_rate, left_bands)
    right_pred = result.right_db + peq_chain_response_db(result.freqs_hz, sample_rate, right_bands)
    l_rms, l_max = _metrics(result.freqs_hz, left_pred, resolved.left_values_db)
    r_rms, r_max = _metrics(result.freqs_hz, right_pred, resolved.right_values_db)

    # Also compute pre-refinement metrics for comparison
    left_pred_orig = result.left_db + peq_chain_response_db(result.freqs_hz, sample_rate, left_bands_orig)
    right_pred_orig = result.right_db + peq_chain_response_db(result.freqs_hz, sample_rate, right_bands_orig)
    l_rms_orig, l_max_orig = _metrics(result.freqs_hz, left_pred_orig, resolved.left_values_db)
    r_rms_orig, r_max_orig = _metrics(result.freqs_hz, right_pred_orig, resolved.right_values_db)

    from dataclasses import asdict
    identity = get_app_identity()
    budget = FilterBudget(max_filters=max(len(left_bands), len(right_bands)))
    report = {
        'generated_by': identity.as_metadata(),
        'mode': 'refine',
        'source_preset': str(preset_path),
        'original_error': {
            'left_rms': l_rms_orig, 'right_rms': r_rms_orig,
            'left_max': l_max_orig, 'right_max': r_max_orig,
        },
        'predicted_left_rms_error_db': l_rms,
        'predicted_right_rms_error_db': r_rms,
        'predicted_left_max_error_db': l_max,
        'predicted_right_max_error_db': r_max,
        'measurement_diagnostics': result.diagnostics,
        'filter_budget': {
            'family': budget.family,
            'max_filters': budget.max_filters,
            'fill_policy': budget.fill_policy,
            'profile': budget.profile,
        },
        'left_bands': [asdict(b) for b in left_bands],
        'right_bands': [asdict(b) for b in right_bands],
    }
    report['confidence'] = summarize_trustworthiness(result, report).to_dict()

    # Write artifacts
    write_fit_artifacts(
        out_dir,
        kind='fit',
        result=result,
        target=target,
        left_bands=left_bands,
        right_bands=right_bands,
        report=report,
        sample_rate=sample_rate,
        write_target_curve_csv=True,
        filter_budget=budget,
    )

    return report


def _refine_channel(
    freqs_hz: np.ndarray,
    measured_db: np.ndarray,
    target_db: np.ndarray,
    bands: List[PEQBand],
    sample_rate: int,
    max_gain_db: float,
    max_q: float,
) -> List[PEQBand]:
    """Refine a set of PEQ bands against a measurement for one channel."""
    if not bands:
        return bands

    eq_target = target_db - measured_db
    objective = FitObjective.from_target(freqs_hz, eq_target, sample_rate)

    # Run joint refinement (same engine as fit_peq uses after greedy placement)
    refined = _refine_bands_jointly(
        objective, bands,
        max_gain_db=max_gain_db,
        max_q=max_q,
    )
    return refined
