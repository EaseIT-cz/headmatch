from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

import yaml

from .peq import PEQBand



def export_camilladsp_filters_yaml(path: str | Path, bands_left: List[PEQBand], bands_right: List[PEQBand], samplerate: int = 48000) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    filters = {}
    left_names, right_names = [], []
    for i, band in enumerate(bands_left, 1):
        name = f'L_{i}_{band.kind}'
        left_names.append(name)
        filters[name] = {
            'type': 'Biquad',
            'parameters': {
                'type': {'peaking': 'Peaking', 'lowshelf': 'Lowshelf', 'highshelf': 'Highshelf'}[band.kind],
                'freq': round(band.freq, 3),
                'q': round(band.q, 4) if band.kind == 'peaking' else round(max(0.1, min(1.0, band.q)), 4),
                'gain': round(band.gain_db, 3),
            },
        }
    for i, band in enumerate(bands_right, 1):
        name = f'R_{i}_{band.kind}'
        right_names.append(name)
        filters[name] = {
            'type': 'Biquad',
            'parameters': {
                'type': {'peaking': 'Peaking', 'lowshelf': 'Lowshelf', 'highshelf': 'Highshelf'}[band.kind],
                'freq': round(band.freq, 3),
                'q': round(band.q, 4) if band.kind == 'peaking' else round(max(0.1, min(1.0, band.q)), 4),
                'gain': round(band.gain_db, 3),
            },
        }

    data = {
        'samplerate': samplerate,
        'channels': {'in': 2, 'out': 2},
        'filters': filters,
        'pipeline': [
            {'channel': 0, 'names': left_names},
            {'channel': 1, 'names': right_names},
        ],
        'devices': {
            'samplerate': samplerate,
            'chunksize': 1024,
            'silence_threshold': -90,
            'silence_timeout': 3.0,
            'capture': {
                'type': 'Pulse',
                'channels': 2,
                'device': 'set-me',
                'format': 'FLOAT32LE',
            },
            'playback': {
                'type': 'Pulse',
                'channels': 2,
                'device': 'set-me',
                'format': 'FLOAT32LE',
            },
        },
    }
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return path



def export_camilladsp_filter_snippet_yaml(path: str | Path, bands_left: List[PEQBand], bands_right: List[PEQBand]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    filters = {}
    pipeline = []
    names = [[], []]
    for ch, bands in enumerate([bands_left, bands_right]):
        for i, band in enumerate(bands, 1):
            name = f'{"L" if ch == 0 else "R"}_{i}_{band.kind}'
            names[ch].append(name)
            filters[name] = {
                'type': 'Biquad',
                'parameters': {
                    'type': {'peaking': 'Peaking', 'lowshelf': 'Lowshelf', 'highshelf': 'Highshelf'}[band.kind],
                    'freq': round(band.freq, 3),
                    'q': round(band.q, 4),
                    'gain': round(band.gain_db, 3),
                }
            }
    pipeline = [{'channel': 0, 'names': names[0]}, {'channel': 1, 'names': names[1]}]
    path.write_text(yaml.safe_dump({'filters': filters, 'pipeline': pipeline}, sort_keys=False))
    return path
