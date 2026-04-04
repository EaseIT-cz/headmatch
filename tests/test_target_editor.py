"""Tests for the target curve editor model."""
from __future__ import annotations

from pathlib import Path
import numpy as np

from headmatch.target_editor import TargetEditor, ControlPoint


def test_default_editor_evaluates_flat():
    editor = TargetEditor()
    freqs, values = editor.evaluate()
    assert len(freqs) > 100
    assert np.max(np.abs(values)) < 0.01


def test_add_point_maintains_order():
    editor = TargetEditor()
    editor.add_point(500.0, 3.0)
    freqs_sorted = [p.freq_hz for p in editor.points]
    assert freqs_sorted == sorted(freqs_sorted)


def test_move_point():
    editor = TargetEditor()
    editor.move_point(2, 2000.0, 5.0)
    assert any(p.freq_hz == 2000.0 and p.gain_db == 5.0 for p in editor.points)


def test_remove_point_keeps_minimum():
    editor = TargetEditor(points=[ControlPoint(100, 0), ControlPoint(1000, 0)])
    editor.remove_point(0)
    assert len(editor.points) == 2  # can't go below 2


def test_evaluate_with_boost():
    editor = TargetEditor(points=[
        ControlPoint(20.0, 0.0),
        ControlPoint(1000.0, 6.0),
        ControlPoint(20000.0, 0.0),
    ])
    freqs, values = editor.evaluate()
    # At 1 kHz the curve should be near 6 dB
    idx_1k = np.argmin(np.abs(freqs - 1000.0))
    assert abs(values[idx_1k] - 6.0) < 0.5


def test_save_and_reload(tmp_path: Path):
    editor = TargetEditor(points=[
        ControlPoint(20.0, -2.0),
        ControlPoint(1000.0, 3.0),
        ControlPoint(20000.0, -1.0),
    ])
    path = str(tmp_path / "custom_target.csv")
    editor.save(path)
    assert Path(path).exists()

    reloaded = TargetEditor.from_csv(path)
    assert len(reloaded.points) >= 3  # at least endpoints plus interior points
    _, orig_values = editor.evaluate()
    _, reload_values = reloaded.evaluate()
    # Should be close but not identical (resampled)
    assert np.max(np.abs(orig_values - reload_values)) < 1.5
