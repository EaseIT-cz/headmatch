from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

import numpy as np

from .io_utils import load_fr_csv, save_fr_csv
from .signals import geometric_log_grid


TargetSemantics = Literal['absolute', 'relative']


@dataclass
class TargetCurve:
    freqs_hz: np.ndarray
    values_db: np.ndarray
    name: str = 'target'
    semantics: TargetSemantics = 'absolute'



def normalize_at_1khz(freqs_hz: np.ndarray, values_db: np.ndarray) -> np.ndarray:
    freqs_hz = np.asarray(freqs_hz, dtype=np.float64)
    values_db = np.asarray(values_db, dtype=np.float64)
    if freqs_hz.shape != values_db.shape:
        raise ValueError('Target curve frequencies and values must have the same shape')
    if len(freqs_hz) < 2:
        raise ValueError('Target curve must contain at least two frequency points')
    if freqs_hz[0] > 1000.0 or freqs_hz[-1] < 1000.0:
        raise ValueError(
            'Target curve must span 1 kHz for normalization. '
            f'Got {freqs_hz[0]:.1f} Hz to {freqs_hz[-1]:.1f} Hz.'
        )
    return values_db - np.interp(1000.0, freqs_hz, values_db)  # type: ignore[no-any-return]



def _read_target_metadata(path: str | Path) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for line in Path(path).read_text(encoding='utf-8-sig').splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if not stripped.startswith('#'):
            break
        payload = stripped[1:].strip()
        if '=' not in payload:
            continue
        key, value = payload.split('=', 1)
        metadata[key.strip().lower()] = value.strip()
    return metadata


def _infer_target_semantics(path: str | Path, metadata: dict[str, str]) -> TargetSemantics:
    explicit = metadata.get('headmatch_target_semantics') or metadata.get('target_semantics')
    if explicit in {'absolute', 'relative'}:
        return explicit  # type: ignore[return-value]
    stem = Path(path).stem.lower()
    if stem.startswith('clone_') or stem.endswith('_clone') or '_to_' in stem:
        return 'relative'
    return 'absolute'


def load_curve(path: str | Path, name: Optional[str] = None, semantics: TargetSemantics | None = None) -> TargetCurve:
    freqs, vals = load_fr_csv(path)
    metadata = _read_target_metadata(path)
    curve_semantics = semantics or _infer_target_semantics(path, metadata)
    return TargetCurve(freqs, normalize_at_1khz(freqs, vals), name or Path(path).stem, curve_semantics)



def resample_curve(curve: TargetCurve, freqs_hz: np.ndarray) -> TargetCurve:
    values = np.interp(freqs_hz, curve.freqs_hz, curve.values_db)
    return TargetCurve(freqs_hz, values, curve.name, curve.semantics)



def create_flat_target(freqs_hz: np.ndarray) -> TargetCurve:
    return TargetCurve(freqs_hz=freqs_hz, values_db=np.zeros_like(freqs_hz), name='flat_1k_norm', semantics='absolute')



def clone_target_from_source_target(source_curve_path: str | Path, target_curve_path: str | Path, out_path: str | Path | None = None) -> TargetCurve:
    source_path = Path(source_curve_path)
    target_path = Path(target_curve_path)
    out_file = Path(out_path) if out_path else None
    if source_path.resolve() == target_path.resolve():
        raise ValueError('Source and target CSV must be different files when building a clone target')
    if out_file and any(out_file.resolve() == candidate.resolve() for candidate in (source_path, target_path)):
        raise ValueError('Output CSV must not overwrite the source or target measurement file')

    grid = geometric_log_grid()
    source = resample_curve(load_curve(source_path, 'source'), grid)
    target = resample_curve(load_curve(target_path, 'target'), grid)
    source_norm = normalize_at_1khz(source.freqs_hz, source.values_db)
    target_norm = normalize_at_1khz(target.freqs_hz, target.values_db)
    diff = target_norm - source_norm
    zero_idx = int(np.argmin(np.abs(grid - 1000.0)))
    diff = diff - diff[zero_idx]
    curve = TargetCurve(freqs_hz=grid, values_db=diff, name=f'clone_{source_path.stem}_to_{target_path.stem}', semantics='relative')
    if out_file:
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text('# headmatch_target_semantics=relative\n', encoding="utf-8")
        with out_file.open('a', encoding='utf-8', newline='') as handle:
            import csv
            writer = csv.writer(handle)
            writer.writerow(['frequency_hz', 'target_db'])
            for f_hz, v in zip(grid, diff):
                writer.writerow([float(f_hz), float(v)])
    return curve
