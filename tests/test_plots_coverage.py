"""Coverage tests for plots.py missing lines 22 and 62."""
from __future__ import annotations

import numpy as np

from headmatch.plots import _grid_lines, _log_x_positions


# ── line 22: degenerate log range (log_max ≈ log_min) → centered positions ──

def test_log_x_positions_degenerate_range():
    freqs = np.array([1000.0, 1000.0, 1000.0])
    width = 800.0
    out = _log_x_positions(freqs, width)
    # All collapse to the horizontal centre of the plot.
    assert np.allclose(out, width * 0.5)
    assert out.shape == freqs.shape


# ── line 62: grid frequencies outside the data range are skipped ──

def test_grid_lines_skips_out_of_range_frequencies():
    # Narrow band 100..200 Hz: the 20/50 Hz ticks fall below freqs[0] and the
    # 500..20000 Hz ticks fall above freqs[-1], so only 100 and 200 draw lines.
    freqs = np.array([100.0, 200.0])
    lines = _grid_lines(freqs, plot_x=10.0, plot_y=10.0, plot_w=400.0, plot_h=200.0)
    text = "\n".join(lines)
    # In-range vertical-grid labels present...
    assert ">100<" in text
    assert ">200<" in text
    # ...out-of-range ticks skipped (no 5k / 20k vertical labels rendered).
    assert ">5k<" not in text
    assert ">20k<" not in text
