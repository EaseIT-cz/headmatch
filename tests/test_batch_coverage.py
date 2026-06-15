"""Coverage tests for batch.py missing lines.

Targets: 92, 105.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from headmatch.batch import load_batch_manifest


# ── line 92: an entry that isn't a JSON object ──

def test_load_manifest_entry_not_object(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"entries": ["not-a-dict"]}), encoding="utf-8")
    with pytest.raises(ValueError, match="Entry 0 must be a JSON object"):
        load_batch_manifest(manifest)


# ── line 105: relative target_csv resolved against manifest parent ──

def test_load_manifest_resolves_relative_target_csv(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "recording": "rec.wav",
                        "out_dir": "out",
                        "target_csv": "targets/harman.csv",
                        "label": "HP",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    entries = load_batch_manifest(manifest)
    assert len(entries) == 1
    expected = str((tmp_path / "targets" / "harman.csv").resolve())
    assert entries[0].target_csv == expected
