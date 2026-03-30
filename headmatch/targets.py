from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from .io_utils import load_fr_csv, save_fr_csv
from .signals import geometric_log_grid


@dataclass
class TargetCurve:
    freqs_hz: np.ndarray
    values_db: np.ndarray
    name: str = 'target'



def normalize_at_1khz(freqs_hz: np.ndarray, values_db: np.ndarray) -> np.ndarray:
    return values_db - np.interp(1000.0, freqs_hz, values_db)



def load_curve(path: str | Path, name: Optional[str] = None) -> TargetCurve:
    freqs, vals = load_fr_csv(path)
    return TargetCurve(freqs, normalize_at_1khz(freqs, vals), name or Path(path).stem)



def resample_curve(curve: TargetCurve, freqs_hz: np.ndarray) -> TargetCurve:
    values = np.interp(freqs_hz, curve.freqs_hz, curve.values_db)
    return TargetCurve(freqs_hz, values, curve.name)



def create_flat_target(freqs_hz: np.ndarray) -> TargetCurve:
    return TargetCurve(freqs_hz=freqs_hz, values_db=np.zeros_like(freqs_hz), name='flat_1k_norm')



def clone_target_from_source_target(source_curve_path: str | Path, target_curve_path: str | Path, out_path: str | Path | None = None) -> TargetCurve:
    grid = geometric_log_grid()
    source = resample_curve(load_curve(source_curve_path, 'source'), grid)
    target = resample_curve(load_curve(target_curve_path, 'target'), grid)
    diff = target.values_db - source.values_db
    curve = TargetCurve(freqs_hz=grid, values_db=diff, name=f'clone_{Path(source_curve_path).stem}_to_{Path(target_curve_path).stem}')
    if out_path:
        save_fr_csv(out_path, grid, diff, 'target_db')
    return curve
