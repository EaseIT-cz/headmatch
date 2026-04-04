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


def test_from_csv_dense_preserves_shape(tmp_path: Path):
    """Loading a dense CSV (48 PPO grid) should produce ~24 points that preserve the shape."""
    freqs = np.geomspace(20, 20000, 479)
    # Create a curve with clear features: bass boost, presence dip, treble shelf
    values = np.zeros_like(freqs)
    values[freqs < 100] = 4.0
    values[(freqs > 3000) & (freqs < 6000)] = -5.0
    values[freqs > 10000] = 2.0
    
    path = str(tmp_path / "dense.csv")
    from headmatch.io_utils import save_fr_csv
    save_fr_csv(path, freqs, values)
    
    editor = TargetEditor.from_csv(path)
    assert len(editor.points) <= 24
    assert len(editor.points) >= 10  # enough to capture the features
    
    # Evaluate and check the shape is preserved at key frequencies
    eval_freqs, eval_values = editor.evaluate(freqs)
    # Bass boost should be present
    bass_mask = eval_freqs < 80
    assert np.mean(eval_values[bass_mask]) > 2.0
    # Presence dip should be present
    dip_mask = (eval_freqs > 3500) & (eval_freqs < 5500)
    assert np.mean(eval_values[dip_mask]) < -2.0


def test_from_csv_small_loads_all_points(tmp_path: Path):
    """A CSV with few points should load all of them."""
    freqs = np.array([20, 100, 1000, 5000, 20000], dtype=float)
    values = np.array([2.0, 1.0, 0.0, -3.0, 1.0])
    
    path = str(tmp_path / "small.csv")
    from headmatch.io_utils import save_fr_csv
    save_fr_csv(path, freqs, values)
    
    editor = TargetEditor.from_csv(path)
    assert len(editor.points) == 5
    assert editor.points[0].freq_hz == 20.0
    assert editor.points[0].gain_db == 2.0
    assert editor.points[4].freq_hz == 20000.0
