from __future__ import annotations

import json

from headmatch.history import load_recent_runs, read_results_guide


def test_load_recent_runs_sorts_latest_first_and_skips_bad_json(tmp_path):
    older = tmp_path / "older"
    older.mkdir()
    (older / "README.txt").write_text("older guide\n")
    (older / "run_summary.json").write_text(
        json.dumps(
            {
                "kind": "fit",
                "out_dir": str(older),
                "sample_rate": 48000,
                "frequency_points": 256,
                "target": "flat",
                "filters": {"left": 4, "right": 4},
                "predicted_error_db": {"left_rms": 1.0, "right_rms": 1.1, "left_max": 3.0, "right_max": 3.1},
                "results_guide": str(older / "README.txt"),
            }
        )
    )
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "run_summary.json").write_text("not-json")
    newer = tmp_path / "newer"
    newer.mkdir()
    (newer / "README.txt").write_text("newer guide\n")
    (newer / "run_summary.json").write_text(
        json.dumps(
            {
                "kind": "iteration",
                "out_dir": str(newer),
                "sample_rate": 48000,
                "frequency_points": 512,
                "target": "custom",
                "filters": {"left": 5, "right": 5},
                "predicted_error_db": {"left_rms": 0.8, "right_rms": 0.9, "left_max": 2.5, "right_max": 2.6},
                "results_guide": str(newer / "README.txt"),
            }
        )
    )

    entries = load_recent_runs(tmp_path)

    assert [entry.summary.out_dir for entry in entries] == [str(newer), str(older)]
    assert entries[0].summary.kind == "iteration"


def test_read_results_guide_returns_fallback_when_missing(tmp_path):
    message = read_results_guide(tmp_path / "missing.txt")
    assert "Results guide not found" in message
