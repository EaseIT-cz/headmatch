from __future__ import annotations

import csv
import json
import re
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



def _normalize_column_name(name: str | None) -> str:
    if not name:
        return ''
    return re.sub(r'[^a-z0-9]+', '_', name.strip().lower()).strip('_')


FREQUENCY_COLUMN_ALIASES = {
    'frequency_hz',
    'frequency',
    'freq',
    'freq_hz',
    'frequency_hz_hz',
    'hz',
}


VALUE_COLUMN_PRIORITY = [
    'response_db',
    'raw',
    'raw_db',
    'fr',
    'target_db',
    'error',
    'equalization',
    'amplitude_db',
    'magnitude_db',
    'level_db',
    'spl',
    'spl_db',
    'db',
]


VALUE_COLUMN_HINTS = (
    'response',
    'raw',
    'target',
    'equalization',
    'error',
    'compensation',
    'magnitude',
    'amplitude',
    'level',
    'spl',
)



def load_fr_csv(path: str | Path) -> Tuple[np.ndarray, np.ndarray]:
    path = Path(path)
    with path.open(newline='', encoding='utf-8-sig') as f:
        raw_lines = [line for line in f if line.strip() and not line.lstrip().startswith('#')]
    if not raw_lines:
        raise ValueError(f'No rows found in {path}')

    reader = csv.DictReader(raw_lines)
    rows = list(reader)
    if not rows:
        raise ValueError(f'No data rows found in {path}')

    original_keys = [key for key in (reader.fieldnames or []) if key is not None]
    normalized_keys = {_normalize_column_name(key): key for key in original_keys}

    freq_key = next((normalized_keys[key] for key in FREQUENCY_COLUMN_ALIASES if key in normalized_keys), None)
    if freq_key is None:
        raise ValueError(
            f'Could not find a frequency column in {path}. Supported names include '
            'frequency_hz, frequency, freq, freq_hz, or hz.'
        )

    value_key = next((normalized_keys[key] for key in VALUE_COLUMN_PRIORITY if key in normalized_keys), None)
    if value_key is None:
        non_freq_pairs = [
            (_normalize_column_name(key), key)
            for key in original_keys
            if key != freq_key
        ]
        hinted = [original for normalized, original in non_freq_pairs if any(hint in normalized for hint in VALUE_COLUMN_HINTS)]
        if hinted:
            value_key = hinted[0]
        elif non_freq_pairs:
            value_key = non_freq_pairs[0][1]
        else:
            raise ValueError(f'Could not find response column in {path}')

    try:
        freqs = np.array([float(r[freq_key]) for r in rows], dtype=np.float64)
        vals = np.array([float(r[value_key]) for r in rows], dtype=np.float64)
    except KeyError as exc:
        raise ValueError(f'Missing expected column {exc.args[0]!r} in {path}') from exc
    except ValueError as exc:
        raise ValueError(f'Could not parse numeric frequency/response data from {path}') from exc

    if freqs.ndim != 1 or vals.ndim != 1 or len(freqs) != len(vals):
        raise ValueError(f'Invalid frequency-response data shape in {path}')
    if len(freqs) < 2:
        raise ValueError(f'{path} must contain at least two frequency rows')
    if np.any(~np.isfinite(freqs)) or np.any(~np.isfinite(vals)):
        raise ValueError(f'{path} contains non-finite frequency or response values')
    if np.any(freqs <= 0):
        raise ValueError(f'{path} contains non-positive frequencies; expected Hz values above 0')
    if len(np.unique(freqs)) != len(freqs):
        raise ValueError(f'{path} contains duplicate frequency values; please deduplicate the CSV first')
    if np.any(np.diff(freqs) <= 0):
        order = np.argsort(freqs)
        freqs = freqs[order]
        vals = vals[order]

    return freqs, vals



def save_json(path: str | Path, data: Dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
