from __future__ import annotations

from pathlib import Path
from typing import List

import yaml

from .app_identity import get_app_identity
from .peq import PEQBand


FILTER_TYPE_NAMES = {'peaking': 'Peaking', 'lowshelf': 'Lowshelf', 'highshelf': 'Highshelf'}



def _band_payload(band: PEQBand) -> dict:
    return {
        'type': FILTER_TYPE_NAMES[band.kind],
        'freq': round(band.freq, 3),
        'q': round(band.q, 4) if band.kind == 'peaking' else round(max(0.1, min(1.0, band.q)), 4),
        'gain': round(band.gain_db, 3),
    }



def _build_filter_bank(bands_left: List[PEQBand], bands_right: List[PEQBand]) -> tuple[dict, list[str], list[str]]:
    filters = {}
    left_names, right_names = [], []
    for channel_prefix, names, bands in (('L', left_names, bands_left), ('R', right_names, bands_right)):
        for i, band in enumerate(bands, 1):
            name = f'{channel_prefix}_{i}_{band.kind}'
            names.append(name)
            filters[name] = {'type': 'Biquad', 'parameters': _band_payload(band)}
    return filters, left_names, right_names



def export_camilladsp_filters_yaml(path: str | Path, bands_left: List[PEQBand], bands_right: List[PEQBand], samplerate: int = 48000) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    filters, left_names, right_names = _build_filter_bank(bands_left, bands_right)
    identity = get_app_identity()
    data = {
        'metadata': {
            'generated_by': identity.as_metadata(),
            'title': 'headmatch CamillaDSP starter config',
            'usage': [
                'Replace capture.device and playback.device with your real CamillaDSP device names.',
                'Keep the per-channel filter lists in pipeline unless you are merging into another config.',
            ],
        },
        'samplerate': samplerate,
        'channels': {'in': 2, 'out': 2},
        'filters': filters,
        'pipeline': [
            {'channel': 0, 'names': left_names, 'description': 'Left headphone channel filters'},
            {'channel': 1, 'names': right_names, 'description': 'Right headphone channel filters'},
        ],
        'devices': {
            'samplerate': samplerate,
            'chunksize': 1024,
            'silence_threshold': -90,
            'silence_timeout': 3.0,
            'capture': {
                'type': 'Pulse',
                'channels': 2,
                'device': 'replace-with-your-input-device',
                'format': 'FLOAT32LE',
            },
            'playback': {
                'type': 'Pulse',
                'channels': 2,
                'device': 'replace-with-your-output-device',
                'format': 'FLOAT32LE',
            },
        },
    }
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return path



def export_camilladsp_filter_snippet_yaml(path: str | Path, bands_left: List[PEQBand], bands_right: List[PEQBand]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    filters, left_names, right_names = _build_filter_bank(bands_left, bands_right)
    identity = get_app_identity()
    payload = {
        'metadata': {
            'generated_by': identity.as_metadata(),
            'title': 'headmatch CamillaDSP filter snippet',
            'usage': 'Merge filters and pipeline into an existing CamillaDSP config.',
        },
        'filters': filters,
        'pipeline': [
            {'channel': 0, 'names': left_names},
            {'channel': 1, 'names': right_names},
        ],
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False))
    return path
