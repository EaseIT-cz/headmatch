"""Tests for the batch-fit workflow."""
import json
from unittest.mock import patch, MagicMock

import pytest

from headmatch.batch import (
    BatchEntry,
    BatchResult,
    generate_manifest_template,
    load_batch_manifest,
    run_batch_fit,
)
from headmatch.signals import SweepSpec


def _make_manifest(tmp_path, entries):
    """Write a manifest JSON and return its path."""
    manifest = tmp_path / "batch_manifest.json"
    manifest.write_text(json.dumps({"entries": entries}, indent=2), encoding="utf-8")
    return manifest


def test_load_batch_manifest_basic(tmp_path):
    rec = tmp_path / "rec.wav"
    rec.touch()
    manifest = _make_manifest(tmp_path, [
        {"recording": "rec.wav", "out_dir": "fit_out", "label": "test"},
    ])
    entries = load_batch_manifest(manifest)
    assert len(entries) == 1
    assert entries[0].label == "test"
    assert entries[0].recording == str((tmp_path / "rec.wav").resolve())
    assert entries[0].out_dir == str((tmp_path / "fit_out").resolve())


def test_load_batch_manifest_missing_recording(tmp_path):
    manifest = _make_manifest(tmp_path, [
        {"out_dir": "fit_out"},
    ])
    with pytest.raises(ValueError, match="missing required 'recording'"):
        load_batch_manifest(manifest)


def test_load_batch_manifest_missing_out_dir(tmp_path):
    manifest = _make_manifest(tmp_path, [
        {"recording": "rec.wav"},
    ])
    with pytest.raises(ValueError, match="missing required 'out_dir'"):
        load_batch_manifest(manifest)


def test_load_batch_manifest_empty_entries(tmp_path):
    manifest = _make_manifest(tmp_path, [])
    with pytest.raises(ValueError, match="non-empty"):
        load_batch_manifest(manifest)


def test_load_batch_manifest_bad_json(tmp_path):
    manifest = tmp_path / "bad.json"
    manifest.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid JSON"):
        load_batch_manifest(manifest)


def test_load_batch_manifest_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_batch_manifest(tmp_path / "missing.json")


def test_load_batch_manifest_wrong_type(tmp_path):
    manifest = tmp_path / "bad.json"
    manifest.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        load_batch_manifest(manifest)


@patch("headmatch.batch.process_single_measurement")
def test_run_batch_fit_success(mock_process, tmp_path):
    """Successful batch run produces results and summary."""
    mock_process.return_value = {
        "predicted_left_rms_error_db": 1.5,
        "predicted_right_rms_error_db": 2.0,
        "confidence": {"label": "high", "score": 85},
    }
    rec = tmp_path / "rec.wav"
    rec.touch()
    manifest = _make_manifest(tmp_path, [
        {"recording": "rec.wav", "out_dir": "fit", "label": "HD650"},
    ])
    spec = SweepSpec(sample_rate=48000, duration_s=3.0)
    results = run_batch_fit(manifest, spec)

    assert len(results) == 1
    assert results[0].success is True
    assert results[0].label == "HD650"
    assert results[0].confidence_label == "high"

    summary_path = tmp_path / "batch_summary.json"
    assert summary_path.exists()
    summary = json.loads(summary_path.read_text())
    assert summary["total"] == 1
    assert summary["succeeded"] == 1


@patch("headmatch.batch.process_single_measurement")
def test_run_batch_fit_partial_failure(mock_process, tmp_path):
    """If one entry fails, the batch continues and records the error."""
    def side_effect(recording_wav, out_dir, sweep_spec, **kw):
        if "bad" in str(recording_wav):
            raise ValueError("bad recording")
        return {
            "predicted_left_rms_error_db": 1.0,
            "predicted_right_rms_error_db": 1.0,
            "confidence": {"label": "high", "score": 90},
        }
    mock_process.side_effect = side_effect

    for name in ("good.wav", "bad.wav"):
        (tmp_path / name).touch()
    manifest = _make_manifest(tmp_path, [
        {"recording": "good.wav", "out_dir": "fit_good", "label": "Good"},
        {"recording": "bad.wav", "out_dir": "fit_bad", "label": "Bad"},
    ])
    spec = SweepSpec(sample_rate=48000, duration_s=3.0)
    results = run_batch_fit(manifest, spec)

    assert len(results) == 2
    assert results[0].success is True
    assert results[1].success is False
    assert "bad recording" in results[1].error


def test_generate_manifest_template(tmp_path):
    out = tmp_path / "template.json"
    result = generate_manifest_template(out, num_entries=2)
    assert result == out
    assert out.exists()
    data = json.loads(out.read_text())
    assert len(data["entries"]) == 2
    assert data["entries"][0]["recording"] == "session_01/recording.wav"
    assert "_comment" in data


@patch("headmatch.batch.process_single_measurement")
def test_run_batch_fit_with_progress_callback(mock_process, tmp_path):
    mock_process.return_value = {
        "predicted_left_rms_error_db": 1.0,
        "predicted_right_rms_error_db": 1.0,
        "confidence": {"label": "high", "score": 90},
    }
    (tmp_path / "rec.wav").touch()
    manifest = _make_manifest(tmp_path, [
        {"recording": "rec.wav", "out_dir": "fit", "label": "Test"},
    ])
    spec = SweepSpec(sample_rate=48000, duration_s=3.0)
    progress_calls = []
    run_batch_fit(manifest, spec, on_progress=lambda i, n, label: progress_calls.append((i, n, label)))
    assert len(progress_calls) == 1
    assert progress_calls[0] == (1, 1, "Test")
