"""Batch-fit workflow for processing multiple recordings in one pass.

Given a manifest file (JSON or YAML) listing recording/target pairs,
runs the analysis → fit → export pipeline for each entry and writes
a consolidated summary.  Useful when measuring multiple headphones
or multiple target curves in a single session.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Optional

from .app_identity import get_app_identity
from .io_utils import save_json
from .peq import FilterBudget
from .pipeline import process_single_measurement
from .pipeline_artifacts import write_fit_artifacts
from .signals import SweepSpec
from .targets import create_flat_target, load_curve


@dataclass
class BatchEntry:
    """One recording/target pair in a batch manifest."""

    recording: str
    out_dir: str
    target_csv: Optional[str] = None
    label: Optional[str] = None


@dataclass
class BatchResult:
    """Result of processing one batch entry."""

    label: str
    out_dir: str
    recording: str
    success: bool
    error: Optional[str] = None
    predicted_left_rms_error_db: Optional[float] = None
    predicted_right_rms_error_db: Optional[float] = None
    confidence_label: Optional[str] = None
    confidence_score: Optional[int] = None


def load_batch_manifest(path: str | Path) -> list[BatchEntry]:
    """Load a batch manifest from a JSON file.

    Expected format::

        {
            "entries": [
                {
                    "recording": "session_01/recording.wav",
                    "out_dir": "session_01/fit",
                    "target_csv": "targets/harman_2019.csv",
                    "label": "HD650 Harman"
                },
                ...
            ]
        }

    Paths are resolved relative to the manifest file's parent directory.
    """
    manifest_path = Path(path).expanduser()
    if not manifest_path.exists():
        raise FileNotFoundError(f"Batch manifest not found: {manifest_path}")

    text = manifest_path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in batch manifest {manifest_path}: {exc}") from exc

    if not isinstance(data, dict) or "entries" not in data:
        raise ValueError(
            f"Batch manifest must be a JSON object with an 'entries' array. "
            f"Got: {type(data).__name__}"
        )

    entries_raw = data["entries"]
    if not isinstance(entries_raw, list) or not entries_raw:
        raise ValueError("Batch manifest 'entries' must be a non-empty array.")

    base = manifest_path.parent
    entries: list[BatchEntry] = []
    for i, raw in enumerate(entries_raw):
        if not isinstance(raw, dict):
            raise ValueError(f"Entry {i} must be a JSON object, got {type(raw).__name__}")
        recording = raw.get("recording")
        if not recording:
            raise ValueError(f"Entry {i} is missing required 'recording' field")
        out_dir = raw.get("out_dir")
        if not out_dir:
            raise ValueError(f"Entry {i} is missing required 'out_dir' field")

        # Resolve relative paths against the manifest's parent directory
        recording_path = str((base / recording).resolve()) if not Path(recording).is_absolute() else recording
        out_dir_path = str((base / out_dir).resolve()) if not Path(out_dir).is_absolute() else out_dir
        target_csv = raw.get("target_csv")
        if target_csv and not Path(target_csv).is_absolute():
            target_csv = str((base / target_csv).resolve())

        entries.append(BatchEntry(
            recording=recording_path,
            out_dir=out_dir_path,
            target_csv=target_csv,
            label=raw.get("label") or Path(recording).stem,
        ))

    return entries


def run_batch_fit(
    manifest_path: str | Path,
    sweep_spec: SweepSpec,
    *,
    max_filters: int = 8,
    filter_budget: FilterBudget | None = None,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> list[BatchResult]:
    """Process all entries in a batch manifest.

    Returns a list of BatchResult objects, one per entry.
    Failures are recorded in the result rather than aborting the batch.
    """
    entries = load_batch_manifest(manifest_path)
    filter_budget = (filter_budget or FilterBudget(max_filters=max_filters)).normalized()
    results: list[BatchResult] = []

    for i, entry in enumerate(entries):
        if on_progress:
            on_progress(i + 1, len(entries), entry.label or entry.recording)

        try:
            report = process_single_measurement(
                recording_wav=entry.recording,
                out_dir=entry.out_dir,
                sweep_spec=sweep_spec,
                target_path=entry.target_csv,
                max_filters=max_filters,
                filter_budget=filter_budget,
            )
            confidence = report.get("confidence", {})
            results.append(BatchResult(
                label=entry.label or Path(entry.recording).stem,
                out_dir=entry.out_dir,
                recording=entry.recording,
                success=True,
                predicted_left_rms_error_db=report.get("predicted_left_rms_error_db"),
                predicted_right_rms_error_db=report.get("predicted_right_rms_error_db"),
                confidence_label=confidence.get("label"),
                confidence_score=confidence.get("score"),
            ))
        except Exception as exc:
            results.append(BatchResult(
                label=entry.label or Path(entry.recording).stem,
                out_dir=entry.out_dir,
                recording=entry.recording,
                success=False,
                error=str(exc),
            ))

    # Write consolidated summary
    manifest_dir = Path(manifest_path).expanduser().parent
    identity = get_app_identity()
    summary = {
        "generated_by": identity.as_metadata(),
        "manifest": str(manifest_path),
        "total": len(results),
        "succeeded": sum(1 for r in results if r.success),
        "failed": sum(1 for r in results if not r.success),
        "results": [asdict(r) for r in results],
    }
    save_json(manifest_dir / "batch_summary.json", summary)

    return results


def generate_manifest_template(out_path: str | Path, *, num_entries: int = 3) -> Path:
    """Write a starter batch manifest template to help first-time users.

    The template includes commented guidance and placeholder entries
    that make the expected structure obvious.
    """
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    entries = []
    for i in range(1, num_entries + 1):
        entries.append({
            "recording": f"session_{i:02d}/recording.wav",
            "out_dir": f"session_{i:02d}/fit",
            "target_csv": None,
            "label": f"Headphone {i}",
        })

    template = {
        "_comment": (
            "HeadMatch batch manifest. "
            "List your recording/target pairs in 'entries'. "
            "Paths are resolved relative to this file. "
            "Set target_csv to null for a flat target."
        ),
        "entries": entries,
    }

    out.write_text(json.dumps(template, indent=2) + "\n", encoding="utf-8")
    return out
