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
    def from_csv(cls, path: str) -> 'TargetEditor':
        """Load control points from an existing target CSV (sample key points)."""
        from .io_utils import load_fr_csv
        freqs, values = load_fr_csv(path)
        # Sample ~8 evenly-spaced points in log frequency
        if len(freqs) <= 8:
            points = [ControlPoint(float(f), float(v)) for f, v in zip(freqs, values)]
        else:
            indices = np.linspace(0, len(freqs) - 1, 8, dtype=int)
            points = [ControlPoint(float(freqs[i]), float(values[i])) for i in indices]
        return cls(points=points)
