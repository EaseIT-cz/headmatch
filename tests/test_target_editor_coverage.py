"""Coverage tests for target_editor.py edge branches."""
from __future__ import annotations

import numpy as np

from headmatch.io_utils import save_fr_csv
from headmatch.target_editor import ControlPoint, TargetEditor


def test_remove_point_pops_when_above_minimum():
    # remove_point actually pops the index when > 2 points remain (line 46).
    editor = TargetEditor(points=[
        ControlPoint(20.0, 0.0),
        ControlPoint(1000.0, 1.0),
        ControlPoint(20000.0, 2.0),
    ])
    editor.remove_point(1)
    assert [p.freq_hz for p in editor.points] == [20.0, 20000.0]


def test_evaluate_with_single_point_returns_zeros():
    # evaluate returns zeros when fewer than 2 control points (line 65).
    editor = TargetEditor(points=[ControlPoint(1000.0, 5.0)])
    freqs = np.array([100.0, 1000.0, 10000.0])
    out_freqs, values = editor.evaluate(freqs)
    assert np.array_equal(out_freqs, freqs)
    assert np.array_equal(values, np.zeros_like(freqs))


def test_from_csv_prunes_excess_peaks_by_prominence(tmp_path):
    # A dense, strongly-oscillating curve produces more peaks/troughs than
    # max_points, exercising the prominence-pruning branch (lines 105-113).
    n = 200
    freqs = np.geomspace(20, 20000, n)
    # Alternating high/low values -> a peak or trough at almost every interior
    # index, so the peak/trough set far exceeds a small max_points budget.
    values = np.where(np.arange(n) % 2 == 0, 1.0, -1.0).astype(float)
    path = str(tmp_path / 'oscillating.csv')
    save_fr_csv(path, freqs, values)

    editor = TargetEditor.from_csv(path, max_points=6)
    assert len(editor.points) <= 6
    # Endpoints are always retained.
    assert editor.points[0].freq_hz == float(freqs[0])
    assert editor.points[-1].freq_hz == float(freqs[-1])
