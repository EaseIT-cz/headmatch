"""A/B comparison helper for switching between EQ presets.

Generates paired preset files from two run summaries so users can
quickly A/B test different EQ configurations in CamillaDSP or
Equalizer APO without manual file juggling.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .contracts import FrontendRunSummary
from .io_utils import save_json


@dataclass(frozen=True)
class ComparisonPair:
    """A pair of runs selected for A/B comparison."""

    label_a: str
    label_b: str
    run_a_dir: Path
    run_b_dir: Path
    summary_a: FrontendRunSummary
    summary_b: FrontendRunSummary


@dataclass(frozen=True)
class ComparisonExport:
    """Result of exporting an A/B comparison."""

    output_dir: Path
    preset_a_apo: Path
    preset_b_apo: Path
    preset_a_cdsp: Path
    preset_b_cdsp: Path
    comparison_json: Path


def load_run_summary(run_dir: str | Path) -> FrontendRunSummary:
    """Load a FrontendRunSummary from a run directory."""
    summary_path = Path(run_dir) / "run_summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"No run_summary.json found in {run_dir}")
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    return FrontendRunSummary.from_dict(payload)


def build_comparison_pair(
    run_a_dir: str | Path,
    run_b_dir: str | Path,
    *,
    label_a: str = "A",
    label_b: str = "B",
) -> ComparisonPair:
    """Build a comparison pair from two run directories."""
    dir_a = Path(run_a_dir)
    dir_b = Path(run_b_dir)
    return ComparisonPair(
        label_a=label_a,
        label_b=label_b,
        run_a_dir=dir_a,
        run_b_dir=dir_b,
        summary_a=load_run_summary(dir_a),
        summary_b=load_run_summary(dir_b),
    )


def _copy_preset(src_dir: Path, dst_dir: Path, filename: str, label: str) -> Path:
    """Copy a preset file with a label prefix."""
    src = src_dir / filename
    dst = dst_dir / f"{label}_{filename}"
    if src.exists():
        shutil.copy2(src, dst)
    return dst


def export_ab_comparison(
    pair: ComparisonPair,
    output_dir: str | Path,
) -> ComparisonExport:
    """Export A/B comparison presets to a single directory.

    Copies the Equalizer APO and CamillaDSP presets from both runs
    into a shared output directory with A_/B_ prefixes, plus a
    comparison.json summarizing the differences.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    preset_a_apo = _copy_preset(pair.run_a_dir, out, "equalizer_apo.txt", pair.label_a)
    preset_b_apo = _copy_preset(pair.run_b_dir, out, "equalizer_apo.txt", pair.label_b)
    preset_a_cdsp = _copy_preset(pair.run_a_dir, out, "camilladsp_full.yaml", pair.label_a)
    preset_b_cdsp = _copy_preset(pair.run_b_dir, out, "camilladsp_full.yaml", pair.label_b)

    # Build comparison summary
    sa = pair.summary_a
    sb = pair.summary_b
    comparison = {
        "label_a": pair.label_a,
        "label_b": pair.label_b,
        "run_a_dir": str(pair.run_a_dir),
        "run_b_dir": str(pair.run_b_dir),
        "comparison": {
            "target": {"a": sa.target, "b": sb.target},
            "filters_left": {"a": sa.filters.left, "b": sb.filters.left},
            "filters_right": {"a": sa.filters.right, "b": sb.filters.right},
            "predicted_error_left_rms": {
                "a": sa.predicted_error_db.left_rms,
                "b": sb.predicted_error_db.left_rms,
            },
            "predicted_error_right_rms": {
                "a": sa.predicted_error_db.right_rms,
                "b": sb.predicted_error_db.right_rms,
            },
            "confidence": {
                "a": {"label": sa.confidence.label, "score": sa.confidence.score},
                "b": {"label": sb.confidence.label, "score": sb.confidence.score},
            },
        },
        "instructions": [
            f"To use preset {pair.label_a}: copy {pair.label_a}_equalizer_apo.txt to your APO config.",
            f"To use preset {pair.label_b}: copy {pair.label_b}_equalizer_apo.txt to your APO config.",
            f"For CamillaDSP: point your config at {pair.label_a}_camilladsp_full.yaml or {pair.label_b}_camilladsp_full.yaml.",
            "Switch between them to hear the difference. The preset with lower RMS error usually sounds closer to the target.",
        ],
    }
    comparison_path = out / "comparison.json"
    save_json(comparison_path, comparison)

    return ComparisonExport(
        output_dir=out,
        preset_a_apo=preset_a_apo,
        preset_b_apo=preset_b_apo,
        preset_a_cdsp=preset_a_cdsp,
        preset_b_cdsp=preset_b_cdsp,
        comparison_json=comparison_path,
    )


def format_comparison_table(pair: ComparisonPair) -> str:
    """Format a human-readable comparison table."""
    sa = pair.summary_a
    sb = pair.summary_b

    lines = [
        f"A/B Comparison: {pair.label_a} vs {pair.label_b}",
        "=" * 60,
        "",
        f"{'Metric':<30s}  {'A':>12s}  {'B':>12s}",
        f"{'-'*30}  {'-'*12}  {'-'*12}",
        f"{'Target':<30s}  {sa.target:>12s}  {sb.target:>12s}",
        f"{'Filters (L/R)':<30s}  {sa.filters.left}/{sa.filters.right:>10}  {sb.filters.left}/{sb.filters.right:>10}",
        f"{'Left RMS error (dB)':<30s}  {sa.predicted_error_db.left_rms:>12.2f}  {sb.predicted_error_db.left_rms:>12.2f}",
        f"{'Right RMS error (dB)':<30s}  {sa.predicted_error_db.right_rms:>12.2f}  {sb.predicted_error_db.right_rms:>12.2f}",
        f"{'Confidence':<30s}  {sa.confidence.label:>12s}  {sb.confidence.label:>12s}",
        f"{'Confidence score':<30s}  {sa.confidence.score:>12d}  {sb.confidence.score:>12d}",
        "",
    ]

    # Verdict
    a_err = (sa.predicted_error_db.left_rms + sa.predicted_error_db.right_rms) / 2
    b_err = (sb.predicted_error_db.left_rms + sb.predicted_error_db.right_rms) / 2
    if abs(a_err - b_err) < 0.1:
        lines.append("Verdict: Both presets are very close in predicted accuracy.")
    elif a_err < b_err:
        lines.append(f"Verdict: {pair.label_a} has lower predicted error ({a_err:.2f} vs {b_err:.2f} dB RMS avg).")
    else:
        lines.append(f"Verdict: {pair.label_b} has lower predicted error ({b_err:.2f} vs {a_err:.2f} dB RMS avg).")

    return "\n".join(lines)
