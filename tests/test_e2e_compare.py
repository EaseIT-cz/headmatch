"""End-to-end tests for the compare-runs and compare-ab workflows.

These exercise the real CLI: two completed `fit` runs (built from two
distinct synthesised headphone recordings) are produced under a shared
root, then:

- ``compare-runs`` must print a side-by-side table that references both
  run folders and their predicted-error metrics (cross-checked against
  each run's ``run_summary.json``).
- ``compare-ab`` must export paired A_/B_ prefixed presets that each
  re-import cleanly through the real Equalizer APO parser into a
  non-empty band list (the round-trip contract), plus a sensible
  ``comparison.json`` verdict artifact.

No hardware, network, or real home directory is used: recordings are
synthesised from published headphone curves, and the autouse conftest
fixture sandboxes HOME / XDG_CONFIG_HOME.
"""
from __future__ import annotations

from pathlib import Path

from headmatch import cli
from headmatch.apo_import import load_apo_preset

from tests.test_integration_cli import (
    _patch_cli_config,
    _read_json,
    _synthetic_sweep_spec,
    flat_target_csv,
)
from tests.test_e2e_fitting import (
    HD650_CSV,
    HD800S_CSV,
    _inject_headset_channels,
)
from headmatch.io_utils import write_wav


def _make_recording(tmp_path: Path, csv_path: Path, name: str) -> Path:
    """Synthesise a stereo recording coloured by a published headphone curve."""
    spec = _synthetic_sweep_spec()
    recording, _ = _inject_headset_channels(spec, csv_path)
    path = tmp_path / name
    write_wav(path, recording, spec.sample_rate)
    return path


def _run_fit(monkeypatch, tmp_path: Path, out_dir: Path, recording: Path, max_filters: int) -> None:
    """Invoke the real `fit` CLI into out_dir, producing a full run."""
    spec = _synthetic_sweep_spec()
    _patch_cli_config(monkeypatch, tmp_path)
    cli.main(
        [
            "fit",
            "--recording", str(recording),
            "--out-dir", str(out_dir),
            "--target-csv", str(flat_target_csv()),
            "--sample-rate", str(spec.sample_rate),
            "--duration", str(spec.duration_s),
            "--pre-silence", str(spec.pre_silence_s),
            "--post-silence", str(spec.post_silence_s),
            "--amplitude", str(spec.amplitude),
            "--max-filters", str(max_filters),
        ]
    )


def _make_two_runs(monkeypatch, tmp_path: Path) -> tuple[Path, Path, Path]:
    """Produce two distinct completed fit runs under a shared root.

    Returns (root, run_a_dir, run_b_dir). The two runs differ both in
    their source headphone curve (HD 650 vs HD 800S) and in their filter
    budget, so their summaries and presets genuinely diverge.
    """
    root = tmp_path / "runs"
    root.mkdir()

    rec_a = _make_recording(tmp_path, HD650_CSV, "rec_a.wav")
    rec_b = _make_recording(tmp_path, HD800S_CSV, "rec_b.wav")

    run_a = root / "run_a"
    run_b = root / "run_b"
    _run_fit(monkeypatch, tmp_path, run_a, rec_a, max_filters=6)
    _run_fit(monkeypatch, tmp_path, run_b, rec_b, max_filters=4)
    return root, run_a, run_b


def test_compare_runs_tabulates_both_runs(monkeypatch, tmp_path, capsys):
    root, run_a, run_b = _make_two_runs(monkeypatch, tmp_path)

    summary_a = _read_json(run_a / "run_summary.json")
    summary_b = _read_json(run_b / "run_summary.json")

    # Sanity: each fit produced its own summary and exports.
    assert summary_a["kind"] == "fit"
    assert summary_b["kind"] == "fit"
    assert (run_a / "equalizer_apo.txt").exists()
    assert (run_b / "equalizer_apo.txt").exists()

    capsys.readouterr()  # discard fit output
    cli.main(["compare-runs", "--root", str(root)])
    out = capsys.readouterr().out

    # The table is a side-by-side comparison referencing both run folders.
    assert "Side-by-side comparison" in out
    assert summary_a["out_dir"] in out
    assert summary_b["out_dir"] in out

    # A predicted-error row is present.
    assert "Predicted error" in out

    # Cross-check at least one actual metric from each run's summary appears
    # in the rendered table (history formats RMS to 2 decimals).
    a_left_rms = f"{summary_a['predicted_error_db']['left_rms']:.2f}"
    b_left_rms = f"{summary_b['predicted_error_db']['left_rms']:.2f}"
    assert f"L rms {a_left_rms}" in out
    assert f"L rms {b_left_rms}" in out

    # Both runs' filter counts are surfaced.
    assert "Filters (L/R)" in out


def test_compare_ab_exports_paired_presets_that_reimport(monkeypatch, tmp_path, capsys):
    root, run_a, run_b = _make_two_runs(monkeypatch, tmp_path)

    summary_a = _read_json(run_a / "run_summary.json")
    summary_b = _read_json(run_b / "run_summary.json")

    ab_out = tmp_path / "ab"
    _patch_cli_config(monkeypatch, tmp_path)
    capsys.readouterr()  # discard prior output
    cli.main(
        [
            "compare-ab",
            "--run-a", str(run_a),
            "--run-b", str(run_b),
            "--label-a", "A",
            "--label-b", "B",
            "--out-dir", str(ab_out),
        ]
    )
    out = capsys.readouterr().out

    # The command prints the A/B comparison table with a verdict.
    assert "A/B Comparison: A vs B" in out
    assert "Verdict:" in out

    # Exact A_/B_ prefixed preset filenames (per ab_compare._copy_preset).
    preset_a = ab_out / "A_equalizer_apo.txt"
    preset_b = ab_out / "B_equalizer_apo.txt"
    assert preset_a.exists(), "expected A_equalizer_apo.txt"
    assert preset_b.exists(), "expected B_equalizer_apo.txt"
    # CamillaDSP presets are also paired.
    assert (ab_out / "A_camilladsp_full.yaml").exists()
    assert (ab_out / "B_camilladsp_full.yaml").exists()

    # Round-trip contract: each exported APO preset re-imports cleanly through
    # the real parser into a non-empty band list.
    for preset in (preset_a, preset_b):
        left_bands, right_bands = load_apo_preset(preset)
        assert left_bands, f"{preset.name} parsed into zero left bands"
        assert right_bands, f"{preset.name} parsed into zero right bands"
        for band in left_bands + right_bands:
            assert band.kind in ("peaking", "lowshelf", "highshelf")
            assert band.freq > 0
            assert band.q > 0

    # Verdict / summary artifact is written and sensible.
    comparison_json = ab_out / "comparison.json"
    assert comparison_json.exists(), "expected comparison.json verdict artifact"
    data = _read_json(comparison_json)
    assert data["label_a"] == "A"
    assert data["label_b"] == "B"
    assert data["run_a_dir"] == str(run_a)
    assert data["run_b_dir"] == str(run_b)

    # The artifact cross-checks against each run's own run_summary.json.
    cmp = data["comparison"]
    assert cmp["target"]["a"] == summary_a["target"]
    assert cmp["target"]["b"] == summary_b["target"]
    assert cmp["predicted_error_left_rms"]["a"] == summary_a["predicted_error_db"]["left_rms"]
    assert cmp["predicted_error_right_rms"]["b"] == summary_b["predicted_error_db"]["right_rms"]
    assert cmp["filters_left"]["a"] == summary_a["filters"]["left"]
    assert cmp["filters_right"]["b"] == summary_b["filters"]["right"]

    # Usage instructions reference the exact exported preset names.
    instructions = "\n".join(data["instructions"])
    assert "A_equalizer_apo.txt" in instructions
    assert "B_equalizer_apo.txt" in instructions
