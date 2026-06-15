"""Coverage tests for ab_compare.py missing lines.

Targets: 171 (verdict where B has lower predicted error).
"""
from __future__ import annotations

import json
from pathlib import Path

from headmatch.ab_compare import build_comparison_pair, format_comparison_table
from headmatch.contracts import (
    ConfidenceSummary,
    FrontendRunSummary,
    RunErrorSummary,
    RunFilterCounts,
)


def _write_run_summary(run_dir: Path, *, left_rms: float, right_rms: float):
    run_dir.mkdir(parents=True, exist_ok=True)
    summary = FrontendRunSummary(
        schema_version=1,
        kind="fit",
        out_dir=str(run_dir),
        sample_rate=48000,
        frequency_points=256,
        target="flat",
        filters=RunFilterCounts(left=5, right=5),
        predicted_error_db=RunErrorSummary(left_rms=left_rms, right_rms=right_rms, left_max=3.0, right_max=3.5),
        generated_by={},
        confidence=ConfidenceSummary(
            score=80, label="high", headline="t", interpretation="t",
            reasons=(), warnings=(), metrics={},
        ),
        plots={},
        results_guide=str(run_dir / "README.txt"),
    )
    (run_dir / "run_summary.json").write_text(json.dumps(summary.to_dict()), encoding="utf-8")


def test_verdict_b_has_lower_error(tmp_path):
    run_a = tmp_path / "a"
    run_b = tmp_path / "b"
    _write_run_summary(run_a, left_rms=3.0, right_rms=3.0)
    _write_run_summary(run_b, left_rms=1.0, right_rms=1.0)
    pair = build_comparison_pair(run_a, run_b, label_a="A", label_b="B")
    table = format_comparison_table(pair)
    assert "B has lower predicted error" in table
