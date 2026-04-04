"""Simple target curve editor model.

Provides a drag-point spline editor model that the GUI can render on a Canvas.
The editor works on HeadMatch's standard 48 PPO geometric grid.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

import numpy as np
from scipy.interpolate import PchipInterpolator

from .signals import geometric_log_grid
from .io_utils import save_fr_csv


@dataclass
class ControlPoint:
    freq_hz: float
    gain_db: float


@dataclass
class TargetEditor:
    """Editable target curve built from control points with monotone cubic interpolation."""

    points: List[ControlPoint] = field(default_factory=lambda: [
        ControlPoint(20.0, 0.0),
        ControlPoint(100.0, 0.0),
        ControlPoint(1000.0, 0.0),
        ControlPoint(5000.0, 0.0),
        ControlPoint(10000.0, 0.0),
        ControlPoint(20000.0, 0.0),
    ])

    def add_point(self, freq_hz: float, gain_db: float) -> None:
        """Add a control point, maintaining frequency order."""
        self.points.append(ControlPoint(freq_hz, gain_db))
        self.points.sort(key=lambda p: p.freq_hz)

    def remove_point(self, index: int) -> None:
        """Remove a control point by index. Must keep at least 2 points."""
        if len(self.points) <= 2:
            return
        self.points.pop(index)

    def move_point(self, index: int, freq_hz: float, gain_db: float) -> None:
        """Move a control point to new coordinates."""
        self.points[index] = ControlPoint(freq_hz, gain_db)
        self.points.sort(key=lambda p: p.freq_hz)

    def evaluate(self, freqs_hz: np.ndarray | None = None) -> Tuple[np.ndarray, np.ndarray]:
        """Evaluate the curve on a frequency grid using PCHIP interpolation.

        Returns (freqs_hz, values_db) on the standard 48 PPO grid.
        """
        if freqs_hz is None:
            freqs_hz = geometric_log_grid(20.0, 20000.0, 48)

        ctrl_freqs = np.array([p.freq_hz for p in self.points])
        ctrl_gains = np.array([p.gain_db for p in self.points])

        if len(ctrl_freqs) < 2:
            return freqs_hz, np.zeros_like(freqs_hz)

        # PCHIP preserves monotonicity and avoids overshoot between control points
        interp = PchipInterpolator(np.log10(ctrl_freqs), ctrl_gains, extrapolate=True)
        values = interp(np.log10(freqs_hz))

        return freqs_hz, values

    def save(self, path: str) -> None:
        """Export the evaluated curve as a standard HeadMatch target CSV."""
        freqs, values = self.evaluate()
        save_fr_csv(path, freqs, values, column_name='response_db')

    @classmethod
    def from_csv(cls, path: str, max_points: int = 24) -> 'TargetEditor':
        """Load control points from an existing target CSV.

        If the CSV has few points (≤ max_points), all are loaded directly.
        For dense CSVs (e.g. 48 PPO measurement grids), the curve is
        downsampled by picking peaks, troughs, endpoints, and evenly-spaced
        fill points to preserve the shape in ~max_points control points.
        """
        from .io_utils import load_fr_csv
        freqs, values = load_fr_csv(path)
        n = len(freqs)
        if n <= max_points:
            points = [ControlPoint(float(f), float(v)) for f, v in zip(freqs, values)]
            return cls(points=points)

        # Always include first and last
        key_indices = {0, n - 1}

        # Find local peaks and troughs
        for i in range(1, n - 1):
            if (values[i] > values[i - 1] and values[i] > values[i + 1]) or \
               (values[i] < values[i - 1] and values[i] < values[i + 1]):
                key_indices.add(i)

        # If too many peaks/troughs, keep only the most prominent
        if len(key_indices) > max_points:
            scored = []
            for i in key_indices:
                if i == 0 or i == n - 1:
                    scored.append((i, float('inf')))
                else:
                    prominence = abs(values[i] - (values[max(0, i-1)] + values[min(n-1, i+1)]) / 2)
                    scored.append((i, prominence))
            scored.sort(key=lambda x: x[1], reverse=True)
            key_indices = {idx for idx, _ in scored[:max_points]}

        # Fill remaining budget with evenly-spaced log samples
        remaining = max_points - len(key_indices)
        if remaining > 0:
            fill = np.linspace(0, n - 1, remaining + 2, dtype=int)[1:-1]
            for idx in fill:
                key_indices.add(int(idx))

        indices = sorted(key_indices)[:max_points]
        points = [ControlPoint(float(freqs[i]), float(values[i])) for i in indices]
        return cls(points=points)
