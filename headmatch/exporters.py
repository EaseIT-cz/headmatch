from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

import yaml

from .app_identity import get_app_identity
from .peq import PEQBand


FILTER_TYPE_NAMES = {'peaking': 'Peaking', 'lowshelf': 'Lowshelf', 'highshelf': 'Highshelf'}
GRAPHICEQ_INTERPOLATION_HEADROOM_DB = 1.5
"""Safety margin for Equalizer APO GraphicEQ interpolation overshoot.

Equalizer APO interpolates between GraphicEQ frequency/gain points using
overlapping parametric bands. Adjacent positive-gain bands can "stack up"
in the interpolation region, producing cumulative gain higher than any
single specified point. This constant adds headroom to prevent clipping.
"""

APO_FILTER_TYPE_NAMES = {'peaking': 'PK', 'lowshelf': 'LS', 'highshelf': 'HS'}



def _shelf_s_to_q(s: float, gain_db: float) -> float:
    """Convert RBJ shelf slope parameter S to equivalent Q for CamillaDSP.

    The RBJ cookbook defines shelf alpha using S (slope). CamillaDSP expects
    Q for shelf filters. The relationship is:
        Q = 1 / sqrt((A + 1/A) * (1/S - 1) + 2)
    where A = 10^(gain_db/40).
    """
    s = max(0.1, min(1.0, s))
    A = 10 ** (abs(gain_db) / 40) if abs(gain_db) > 0.01 else 1.0
    inner = (A + 1.0 / A) * (1.0 / s - 1.0) + 2.0
    if inner <= 0:
        return 0.707
    return round(1.0 / (inner ** 0.5), 4)


def _band_payload(band: PEQBand) -> dict:
    if band.kind == 'peaking':
        q = round(band.q, 4)
    else:
        # Shelf filters: use the band's shelf_q property which computes
        # true Q from the explicit slope (or legacy q-as-slope fallback).
        q = round(band.shelf_q, 4)
    return {
        'type': FILTER_TYPE_NAMES[band.kind],
        'freq': round(band.freq, 3),
        'q': q,
        'gain': round(band.gain_db, 3),
    }



def _bands_sorted_by_frequency(bands: Iterable[PEQBand]) -> list[PEQBand]:
    return sorted(bands, key=lambda band: (band.freq, band.kind, band.q, band.gain_db))


def _build_filter_bank(bands_left: List[PEQBand], bands_right: List[PEQBand]) -> tuple[dict, list[str], list[str]]:
    filters = {}
    left_names, right_names = [], []
    for channel_prefix, names, bands in (('L', left_names, bands_left), ('R', right_names, bands_right)):
        for i, band in enumerate(_bands_sorted_by_frequency(bands), 1):
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
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
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
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def _apo_preamp_db(bands: Iterable[PEQBand]) -> float:
    boost = max((band.gain_db for band in bands), default=0.0)
    preamp = round(-max(0.0, boost), 2)
    return 0.0 if abs(preamp) < 0.005 else preamp


def _format_apo_channel(channel: str, bands: List[PEQBand]) -> list[str]:
    lines = [f'Channel: {channel}', f'Preamp: {_apo_preamp_db(bands):.2f} dB']
    for index, band in enumerate(_bands_sorted_by_frequency(bands), 1):
        lines.append(
            f'Filter {index}: ON {APO_FILTER_TYPE_NAMES[band.kind]} '
            f'Fc {band.freq:.2f} Hz Gain {band.gain_db:.2f} dB Q {band.q:.2f}'
        )
    return lines


def export_equalizer_apo_parametric_txt(path: str | Path, bands_left: List[PEQBand], bands_right: List[PEQBand]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        '; headmatch Equalizer APO parametric preset',
        '; Generated for stereo headphones with per-channel filter sections.',
        '',
        *_format_apo_channel('L', bands_left),
        '',
        *_format_apo_channel('R', bands_right),
        '',
    ]
    path.write_text('\n'.join(lines), encoding="utf-8")
    return path


def _format_graphiceq_series(freqs_hz: Iterable[float], gains_db: Iterable[float]) -> str:
    entries = [f'{float(freq):.2f} {float(gain):.2f}' for freq, gain in zip(freqs_hz, gains_db)]
    return 'GraphicEQ: ' + '; '.join(entries)


def export_equalizer_apo_graphiceq_txt(
    path: str | Path,
    freqs_hz: Iterable[float],
    gains_left_db: Iterable[float],
    gains_right_db: Iterable[float],
    *,
    comment: str = '; Generated from the shared effective correction target on the analysis frequency grid.',
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    freqs_hz = list(freqs_hz)
    gains_left_db = list(gains_left_db)
    gains_right_db = list(gains_right_db)
    lines = [
        '; headmatch Equalizer APO GraphicEQ preset',
        comment,
        '',
        'Channel: L',
        f'Preamp: {round(-max(0.0, max(gains_left_db, default=0.0)) - GRAPHICEQ_INTERPOLATION_HEADROOM_DB, 2):.2f} dB',
        _format_graphiceq_series(freqs_hz, gains_left_db),
        '',
        'Channel: R',
        f'Preamp: {round(-max(0.0, max(gains_right_db, default=0.0)) - GRAPHICEQ_INTERPOLATION_HEADROOM_DB, 2):.2f} dB',
        _format_graphiceq_series(freqs_hz, gains_right_db),
        '',
    ]
    path.write_text('\n'.join(lines), encoding="utf-8")
    return path
