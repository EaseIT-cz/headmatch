"""Coverage tests for history.py missing lines.

Targets: 44, 63, 66-67, 164-176.
"""
from __future__ import annotations

import json
from pathlib import Path

from headmatch.contracts import (
    ConfidenceSummary,
    FrontendRunSummary,
    RunErrorSummary,
    RunFilterCounts,
)
from headmatch.history import (
    RunHistoryEntry,
    build_run_comparison,
    format_comparison_table,
    load_recent_runs,
)


def _summary_dict(out_dir: Path, *, results_guide: str, kind="fit", warnings=None):
    return {
        "kind": kind,
        "out_dir": str(out_dir),
        "sample_rate": 48000,
        "frequency_points": 256,
        "target": "flat",
        "filters": {"left": 4, "right": 4},
        "predicted_error_db": {"left_rms": 1.0, "right_rms": 1.1, "left_max": 3.0, "right_max": 3.1},
        "confidence": {
            "score": 90,
            "label": "high",
            "headline": "Trustworthy.",
            "interpretation": "Clean.",
            "reasons": [],
            "warnings": warnings or [],
            "metrics": {},
        },
        "results_guide": results_guide,
    }


# ── line 44: _iter_summary_files returns () when root missing ──

def test_load_recent_runs_missing_root(tmp_path):
    entries = load_recent_runs(tmp_path / "nope")
    assert entries == []


# ── line 63: relative results_guide resolved against summary parent ──

def test_load_recent_runs_relative_guide(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    (run / "README.txt").write_text("guide\n")
    # results_guide is a bare relative filename, not absolute.
    (run / "run_summary.json").write_text(
        json.dumps(_summary_dict(run, results_guide="README.txt"))
    )
    entries = load_recent_runs(tmp_path)
    assert len(entries) == 1
    assert entries[0].guide_path == (run / "README.txt").resolve()
    assert entries[0].guide_path.is_absolute()


# ── lines 66-67: limit break ──

def test_load_recent_runs_respects_limit(tmp_path):
    for i in range(4):
        run = tmp_path / f"run{i}"
        run.mkdir()
        (run / "README.txt").write_text("g\n")
        (run / "run_summary.json").write_text(
            json.dumps(_summary_dict(run, results_guide=str(run / "README.txt")))
        )
    entries = load_recent_runs(tmp_path, limit=2)
    assert len(entries) == 2


# ── lines 164-176: format_comparison_table ──

def _entry(tmp_path: Path, name: str, *, target: str, warnings) -> RunHistoryEntry:
    out = tmp_path / name
    summary = FrontendRunSummary(
        schema_version=1,
        kind="fit",
        out_dir=str(out),
        sample_rate=48000,
        frequency_points=256,
        target=target,
        filters=RunFilterCounts(left=4, right=5),
        predicted_error_db=RunErrorSummary(left_rms=1.0, right_rms=1.1, left_max=3.0, right_max=3.1),
        generated_by={},
        plots={},
        results_guide="",
        confidence=ConfidenceSummary(
            score=88, label="high", headline="ok",
            interpretation="fine", reasons=(), warnings=tuple(warnings), metrics={},
        ),
    )
    return RunHistoryEntry(
        summary_path=out / "run_summary.json", summary=summary, guide_path=out / "README.txt"
    )


def test_format_comparison_table(tmp_path):
    left = _entry(tmp_path, "left", target="custom", warnings=["w1", "w2"])
    right = _entry(tmp_path, "right", target="flat", warnings=[])
    comparison = build_run_comparison([left, right])
    assert comparison is not None
    table = format_comparison_table(comparison)
    assert "Side-by-side comparison" in table
    assert str((tmp_path / "left")) in table
    assert str((tmp_path / "right")) in table
    assert "Target" in table
    assert "A: custom" in table
    assert "B: flat" in table
