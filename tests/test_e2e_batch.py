"""End-to-end test of the batch-fit workflow via the CLI.

A JSON manifest listing two genuinely different synthetic recordings (one
HD 650-colored, one HD 800S-colored) is processed in a single `batch-fit`
run.  The test proves that:

- a consolidated ``batch_summary.json`` is written next to the manifest and
  lists both entries with success status, and
- each entry gets its own output folder with the standard EQ exports AND a
  correcting EQ (predicted error after the fit is lower than before).

It also checks that ``batch-template`` writes a parseable manifest template.

No hardware / network / real home (conftest sandboxes HOME/XDG); everything
is synthesised from a deterministic log sweep.
"""
from __future__ import annotations

import json
from pathlib import Path

from headmatch import cli
from headmatch.io_utils import write_wav

from tests.test_integration_cli import (
    _patch_cli_config,
    _predicted_errors,
    _read_json,
    _synthetic_sweep_spec,
)
from tests.test_e2e_fitting import (
    HD650_CSV,
    HD800S_CSV,
    _inject_headset_channels,
)


def _write_synthetic_recording(path: Path, spec, csv_path: Path) -> None:
    """Write a stereo recording colored by a real published headphone curve."""
    recording, _curve = _inject_headset_channels(spec, csv_path)
    write_wav(path, recording, spec.sample_rate)


def _sweep_args(spec) -> list[str]:
    return [
        "--sample-rate", str(spec.sample_rate),
        "--duration", str(spec.duration_s),
        "--pre-silence", str(spec.pre_silence_s),
        "--post-silence", str(spec.post_silence_s),
        "--amplitude", str(spec.amplitude),
    ]


def test_batch_fit_cli_end_to_end_corrects_every_entry(monkeypatch, tmp_path: Path):
    spec = _synthetic_sweep_spec()
    _patch_cli_config(monkeypatch, tmp_path)

    # Two genuinely distinct recordings: HD 650 vs HD 800S coloration.
    rec_hd650 = tmp_path / "hd650" / "recording.wav"
    rec_hd800s = tmp_path / "hd800s" / "recording.wav"
    rec_hd650.parent.mkdir(parents=True, exist_ok=True)
    rec_hd800s.parent.mkdir(parents=True, exist_ok=True)
    _write_synthetic_recording(rec_hd650, spec, HD650_CSV)
    _write_synthetic_recording(rec_hd800s, spec, HD800S_CSV)

    # Manifest with relative paths, resolved against the manifest's parent.
    # target_csv=null means a flat target.
    manifest = tmp_path / "batch_manifest.json"
    entries = [
        {"recording": "hd650/recording.wav", "out_dir": "hd650/fit", "target_csv": None, "label": "HD650"},
        {"recording": "hd800s/recording.wav", "out_dir": "hd800s/fit", "target_csv": None, "label": "HD800S"},
    ]
    manifest.write_text(json.dumps({"entries": entries}, indent=2), encoding="utf-8")

    cli.main(["batch-fit", "--manifest", str(manifest), *_sweep_args(spec), "--max-filters", "5"])

    # (1) Consolidated summary written next to the manifest.
    summary_path = tmp_path / "batch_summary.json"
    assert summary_path.exists(), "batch_summary.json not written next to manifest"
    summary = _read_json(summary_path)
    assert summary["total"] == 2
    assert summary["succeeded"] == 2
    assert summary["failed"] == 0

    results = summary["results"]
    assert {r["label"] for r in results} == {"HD650", "HD800S"}
    for r in results:
        assert r["success"] is True
        assert r["error"] is None
        assert r["predicted_left_rms_error_db"] is not None
        assert r["predicted_right_rms_error_db"] is not None

    # (2) Each entry's output folder has the standard exports AND a correcting EQ.
    for label, out_dir in (("HD650", tmp_path / "hd650" / "fit"), ("HD800S", tmp_path / "hd800s" / "fit")):
        for name in ("equalizer_apo.txt", "equalizer_apo_graphiceq.txt", "measurement_left.csv", "fit_report.json"):
            assert (out_dir / name).exists(), f"{label}: missing {name}"

        errs = _predicted_errors(out_dir, spec.sample_rate)
        assert errs["left_after"] < errs["left_before"], (
            f"{label}: left EQ did not correct ({errs['left_after']:.2f} >= {errs['left_before']:.2f})"
        )
        assert errs["right_after"] < errs["right_before"], (
            f"{label}: right EQ did not correct ({errs['right_after']:.2f} >= {errs['right_before']:.2f})"
        )

        # The summary's predicted error matches the entry's actual fit report.
        report = _read_json(out_dir / "fit_report.json")
        result = next(r for r in results if r["label"] == label)
        assert abs(result["predicted_left_rms_error_db"] - report["predicted_left_rms_error_db"]) < 1e-6
        assert abs(result["predicted_right_rms_error_db"] - report["predicted_right_rms_error_db"]) < 1e-6


def test_batch_template_cli_writes_parseable_manifest(monkeypatch, tmp_path: Path):
    _patch_cli_config(monkeypatch, tmp_path)
    template_path = tmp_path / "template.json"

    cli.main(["batch-template", "--out", str(template_path), "--entries", "2"])

    assert template_path.exists()
    data = _read_json(template_path)
    assert "_comment" in data
    assert isinstance(data["entries"], list)
    assert len(data["entries"]) == 2
    for entry in data["entries"]:
        assert "recording" in entry
        assert "out_dir" in entry
        assert "target_csv" in entry
        assert "label" in entry
