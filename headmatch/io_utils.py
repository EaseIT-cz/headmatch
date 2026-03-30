from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import soundfile as sf



def write_wav(path: str | Path, data: np.ndarray, sample_rate: int) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), data, sample_rate)



def read_wav(path: str | Path) -> Tuple[np.ndarray, int]:
    data, sr = sf.read(str(path), always_2d=True)
    return data.astype(np.float64), sr



def save_fr_csv(path: str | Path, freqs_hz: np.ndarray, values_db: np.ndarray, column_name: str = 'response_db') -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['frequency_hz', column_name])
        for f_hz, v in zip(freqs_hz, values_db):
            writer.writerow([float(f_hz), float(v)])



def load_fr_csv(path: str | Path) -> Tuple[np.ndarray, np.ndarray]:
    path = Path(path)
    with path.open() as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if not rows:
        raise ValueError(f'No rows found in {path}')

    keys = set(rows[0].keys())
    freq_key = 'frequency_hz' if 'frequency_hz' in keys else 'frequency'
    value_key = None
    for candidate in ['response_db', 'raw', 'raw_db', 'fr', 'target_db', 'error', 'equalization']:
        if candidate in keys:
            value_key = candidate
            break
    if value_key is None:
        # Heuristic for AutoEq style CSVs: use raw first.
        non_freq = [k for k in rows[0].keys() if k != freq_key]
        if not non_freq:
            raise ValueError(f'Could not find response column in {path}')
        value_key = non_freq[0]
    freqs = np.array([float(r[freq_key]) for r in rows], dtype=np.float64)
    vals = np.array([float(r[value_key]) for r in rows], dtype=np.float64)
    return freqs, vals



def save_json(path: str | Path, data: Dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
