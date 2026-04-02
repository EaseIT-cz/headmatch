from __future__ import annotations

import numpy as np
import yaml

from headmatch.exporters import (
    export_camilladsp_filter_snippet_yaml,
    export_camilladsp_filters_yaml,
    export_equalizer_apo_parametric_txt,
)
from headmatch.peq import PEQBand, fit_peq
from headmatch.signals import geometric_log_grid


def test_fit_peq_prefers_broad_shelves_for_edge_tilt():
    freqs = geometric_log_grid()
    target = np.zeros_like(freqs)
    target[freqs <= 120] = 4.0
    target[freqs >= 8000] = -3.0

    bands = fit_peq(freqs, target, sample_rate=48000, max_filters=6)

    kinds = [band.kind for band in bands]
    assert 'lowshelf' in kinds
    assert 'highshelf' in kinds
    assert all(band.q <= 3.0 for band in bands if band.freq > 6000 and band.kind == 'peaking')


def test_fit_peq_respects_filter_budget_when_edge_shelves_trigger():
    freqs = geometric_log_grid()
    target = np.zeros_like(freqs)
    target[freqs <= 120] = 4.0
    target[freqs >= 8000] = -3.0

    bands = fit_peq(freqs, target, sample_rate=48000, max_filters=1)

    assert len(bands) == 1
    assert bands[0].kind in {'lowshelf', 'highshelf'}


def test_fit_peq_returns_no_bands_when_filter_budget_is_zero():
    freqs = geometric_log_grid()
    target = np.zeros_like(freqs)
    target[freqs <= 120] = 4.0
    target[freqs >= 8000] = -3.0

    assert fit_peq(freqs, target, sample_rate=48000, max_filters=0) == []


def test_export_camilladsp_full_yaml_includes_clear_placeholders_and_metadata(tmp_path):
    out = tmp_path / 'camilla.yaml'
    export_camilladsp_filters_yaml(
        out,
        [PEQBand('lowshelf', 105.0, 3.5, 0.7), PEQBand('peaking', 2500.0, -2.0, 1.2)],
        [PEQBand('highshelf', 8500.0, -1.5, 0.7)],
        samplerate=44100,
    )

    payload = yaml.safe_load(out.read_text())

    assert payload['metadata']['title'] == 'headmatch CamillaDSP starter config'
    assert 'Replace capture.device and playback.device' in payload['metadata']['usage'][0]
    assert payload['devices']['capture']['device'] == 'replace-with-your-input-device'
    assert payload['devices']['playback']['device'] == 'replace-with-your-output-device'
    assert payload['pipeline'][0]['description'] == 'Left headphone channel filters'
    assert payload['pipeline'][1]['description'] == 'Right headphone channel filters'
    assert payload['filters']['L_1_lowshelf']['parameters']['q'] == 0.7


def test_export_camilladsp_snippet_uses_same_filter_payloads(tmp_path):
    out = tmp_path / 'snippet.yaml'
    export_camilladsp_filter_snippet_yaml(
        out,
        [PEQBand('peaking', 1000.0, 1.25, 2.75)],
        [PEQBand('highshelf', 9000.0, -2.0, 1.5)],
    )

    payload = yaml.safe_load(out.read_text())

    assert payload['metadata']['title'] == 'headmatch CamillaDSP filter snippet'
    assert payload['filters']['L_1_peaking']['parameters']['q'] == 2.75
    assert payload['filters']['R_1_highshelf']['parameters']['q'] == 1.0
    assert payload['pipeline'][0]['names'] == ['L_1_peaking']
    assert payload['pipeline'][1]['names'] == ['R_1_highshelf']


def test_export_equalizer_apo_parametric_txt_uses_preamp_and_filter_lines(tmp_path):
    out = tmp_path / 'equalizer_apo.txt'
    export_equalizer_apo_parametric_txt(
        out,
        [PEQBand('lowshelf', 105.0, 3.5, 0.7), PEQBand('peaking', 2500.0, -2.0, 1.23)],
        [PEQBand('highshelf', 8500.0, -1.5, 0.7)],
    )

    text = out.read_text()

    assert '; headmatch Equalizer APO parametric preset' in text
    assert 'Channel: L' in text
    assert 'Preamp: -3.50 dB' in text
    assert 'Filter 1: ON LS Fc 105.00 Hz Gain 3.50 dB Q 0.70' in text
    assert 'Filter 2: ON PK Fc 2500.00 Hz Gain -2.00 dB Q 1.23' in text
    assert 'Channel: R' in text
    assert 'Preamp: 0.00 dB' in text
    assert 'Filter 1: ON HS Fc 8500.00 Hz Gain -1.50 dB Q 0.70' in text
