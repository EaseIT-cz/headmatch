"""Tests for the A/B comparison module."""
import json
from pathlib import Path

import pytest

from headmatch.ab_compare import (
    ComparisonPair,
    build_comparison_pair,
    export_ab_comparison,
    format_comparison_table,
    load_run_summary,
)
from headmatch.contracts import (
    ConfidenceSummary,
    FrontendRunSummary,
    RunErrorSummary,
    RunFilterCounts,
)


def _write_run_summary(run_dir: Path, *, target="flat", confidence_label="high", score=85, left_rms=1.0, right_rms=1.2):
    """Helper to write a minimal run_summary.json."""
    run_dir.mkdir(parents=True, exist_ok=True)
    summary = FrontendRunSummary(
        schema_version=1,
        kind="fit",
        out_dir=str(run_dir),
        sample_rate=48000,
        frequency_points=256,
        target=target,
        filters=RunFilterCounts(left=5, right=5),
        predicted_error_db=RunErrorSummary(left_rms=left_rms, right_rms=right_rms, left_max=3.0, right_max=3.5),
        generated_by={"version": "0.4.6"},
        confidence=ConfidenceSummary(
            score=score, label=confidence_label, headline="Test",
            interpretation="Test run", reasons=(), warnings=(), metrics={},
        ),
        plots={},
        results_guide=str(run_dir / "README.txt"),
    )
    (run_dir / "run_summary.json").write_text(json.dumps(summary.to_dict(), indent=2), encoding="utf-8")
    # Write dummy presets
    (run_dir / "equalizer_apo.txt").write_text("Preamp: -3.0 dB\n", encoding="utf-8")
    (run_dir / "camilladsp_full.yaml").write_text("filters: []\n", encoding="utf-8")
    return summary


def test_load_run_summary(tmp_path):
    run_dir = tmp_path / "run1"
    _write_run_summary(run_dir)
    summary = load_run_summary(run_dir)
    assert summary.kind == "fit"
    assert summary.sample_rate == 48000


def test_load_run_summary_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_run_summary(tmp_path / "missing")


def test_build_comparison_pair(tmp_path):
    run_a = tmp_path / "run_a"
    run_b = tmp_path / "run_b"
    _write_run_summary(run_a, target="harman")
    _write_run_summary(run_b, target="flat")
    pair = build_comparison_pair(run_a, run_b, label_a="Harman", label_b="Flat")
    assert pair.label_a == "Harman"
    assert pair.summary_a.target == "harman"
    assert pair.summary_b.target == "flat"


def test_export_ab_comparison(tmp_path):
    run_a = tmp_path / "run_a"
    run_b = tmp_path / "run_b"
    _write_run_summary(run_a, target="harman", left_rms=1.0, right_rms=1.2)
    _write_run_summary(run_b, target="flat", left_rms=2.0, right_rms=2.5)
    pair = build_comparison_pair(run_a, run_b, label_a="A", label_b="B")
    export = export_ab_comparison(pair, tmp_path / "ab_out")
    assert export.output_dir.exists()
    assert export.comparison_json.exists()
    assert export.preset_a_apo.exists()
    assert export.preset_b_apo.exists()
    # Check comparison content
    data = json.loads(export.comparison_json.read_text())
    assert data["label_a"] == "A"
    assert data["comparison"]["target"]["a"] == "harman"
    assert len(data["instructions"]) == 4


def test_format_comparison_table(tmp_path):
    run_a = tmp_path / "run_a"
    run_b = tmp_path / "run_b"
    _write_run_summary(run_a, left_rms=1.0, right_rms=1.0, confidence_label="high", score=90)
    _write_run_summary(run_b, left_rms=2.0, right_rms=2.0, confidence_label="medium", score=60)
    pair = build_comparison_pair(run_a, run_b, label_a="Good", label_b="Bad")
    table = format_comparison_table(pair)
    assert "Good vs Bad" in table
    assert "Verdict:" in table
    assert "Good has lower predicted error" in table


def test_format_comparison_table_close_results(tmp_path):
    run_a = tmp_path / "run_a"
    run_b = tmp_path / "run_b"
    _write_run_summary(run_a, left_rms=1.0, right_rms=1.0)
    _write_run_summary(run_b, left_rms=1.05, right_rms=1.05)
    pair = build_comparison_pair(run_a, run_b)
    table = format_comparison_table(pair)
    assert "very close" in table
