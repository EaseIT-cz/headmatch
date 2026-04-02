from __future__ import annotations

import numpy as np
import yaml

from headmatch.exporters import (
    export_camilladsp_filter_snippet_yaml,
    export_camilladsp_filters_yaml,
    export_equalizer_apo_graphiceq_txt,
    export_equalizer_apo_parametric_txt,
)
from headmatch.peq import FilterBudget, PEQBand, fit_peq, graphic_eq_profile, peq_chain_response_db
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




def test_fit_peq_exact_n_fills_remaining_budget_for_small_targets():
    freqs = geometric_log_grid()
    target = np.zeros_like(freqs)
    target += 0.18 * np.exp(-0.5 * (np.log2(freqs / 1200.0) / 0.55) ** 2)

    up_to_n = fit_peq(freqs, target, sample_rate=48000, budget=FilterBudget(max_filters=4, fill_policy='up_to_n'))
    exact_n = fit_peq(freqs, target, sample_rate=48000, budget=FilterBudget(max_filters=4, fill_policy='exact_n'))

    assert len(up_to_n) < 4
    assert len(exact_n) == 4


def test_fit_peq_exact_n_can_fill_budget_even_when_nearby_rejections_block_conservative_mode(monkeypatch):
    freqs = geometric_log_grid()
    target = np.zeros_like(freqs)
    target += 0.2 * np.exp(-0.5 * (np.log2(freqs / 2500.0) / 0.24) ** 2)

    original = fit_peq.__globals__['_nearby_same_sign_band_exists']

    def always_reject_nearby(bands, candidate):
        return candidate.kind == 'peaking'

    monkeypatch.setitem(fit_peq.__globals__, '_nearby_same_sign_band_exists', always_reject_nearby)
    try:
        up_to_n = fit_peq(freqs, target, sample_rate=48000, budget=FilterBudget(max_filters=3, fill_policy='up_to_n'))
        exact_n = fit_peq(freqs, target, sample_rate=48000, budget=FilterBudget(max_filters=3, fill_policy='exact_n'))
    finally:
        monkeypatch.setitem(fit_peq.__globals__, '_nearby_same_sign_band_exists', original)

    assert up_to_n == []
    assert len(exact_n) == 3

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


def test_export_equalizer_apo_orders_filters_by_frequency(tmp_path):
    out = tmp_path / 'equalizer_apo_sorted.txt'
    export_equalizer_apo_parametric_txt(
        out,
        [
            PEQBand('peaking', 3055.84, 1.91, 0.66),
            PEQBand('lowshelf', 105.0, 4.73, 0.7),
            PEQBand('peaking', 155.68, 1.44, 0.45),
        ],
        [],
    )

    lines = out.read_text().splitlines()
    filter_lines = [line for line in lines if line.startswith('Filter ')]

    assert filter_lines == [
        'Filter 1: ON LS Fc 105.00 Hz Gain 4.73 dB Q 0.70',
        'Filter 2: ON PK Fc 155.68 Hz Gain 1.44 dB Q 0.45',
        'Filter 3: ON PK Fc 3055.84 Hz Gain 1.91 dB Q 0.66',
    ]


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


def test_export_equalizer_apo_parametric_txt_keeps_channel_numbering_independent_and_trailing_newline(tmp_path):
    out = tmp_path / 'equalizer_apo_channels.txt'
    export_equalizer_apo_parametric_txt(
        out,
        [],
        [
            PEQBand('peaking', 3000.0, 1.5, 1.1),
            PEQBand('lowshelf', 90.0, 2.0, 0.7),
        ],
    )

    text = out.read_text()
    lines = text.splitlines()
    right_section = lines[lines.index('Channel: R'):]

    assert text.endswith('\n')
    assert right_section[:4] == [
        'Channel: R',
        'Preamp: -2.00 dB',
        'Filter 1: ON LS Fc 90.00 Hz Gain 2.00 dB Q 0.70',
        'Filter 2: ON PK Fc 3000.00 Hz Gain 1.50 dB Q 1.10',
    ]


def test_export_equalizer_apo_graphiceq_txt_uses_official_graphiceq_syntax(tmp_path):
    out = tmp_path / 'equalizer_apo_graphiceq.txt'
    export_equalizer_apo_graphiceq_txt(
        out,
        [20.0, 1000.0, 20000.0],
        [3.5, -1.25, 0.0],
        [0.0, 1.0, -2.5],
    )

    text = out.read_text()

    assert '; headmatch Equalizer APO GraphicEQ preset' in text
    assert 'Channel: L' in text
    assert 'Preamp: -3.50 dB' in text
    assert 'GraphicEQ: 20.00 3.50; 1000.00 -1.25; 20000.00 0.00' in text
    assert 'Channel: R' in text
    assert 'Preamp: -1.00 dB' in text
    assert 'GraphicEQ: 20.00 0.00; 1000.00 1.00; 20000.00 -2.50' in text



def test_fit_peq_supports_fixed_band_graphiceq_profiles():
    freqs = geometric_log_grid()
    target = np.zeros_like(freqs)
    target += 4.0 * np.exp(-0.5 * (np.log2(freqs / 1000.0) / 0.55) ** 2)
    target += -3.0 * np.exp(-0.5 * (np.log2(freqs / 8000.0) / 0.45) ** 2)

    bands = fit_peq(
        freqs,
        target,
        sample_rate=48000,
        budget=FilterBudget(family='graphic_eq', max_filters=10, profile='geq_10_band'),
    )

    profile = graphic_eq_profile('geq_10_band')
    assert len(bands) == len(profile.freqs_hz)
    assert [round(band.freq, 2) for band in bands] == [round(freq, 2) for freq in profile.freqs_hz]
    assert {round(band.q, 4) for band in bands} == {round(profile.q, 4)}
    assert any(abs(band.gain_db) > 0.25 for band in bands)


def test_graphiceq_exporter_accepts_direct_fit_comment(tmp_path):
    out = tmp_path / 'equalizer_apo_fixed_graphiceq.txt'
    export_equalizer_apo_graphiceq_txt(
        out,
        [31.25, 62.5, 125.0],
        [1.5, -0.5, 0.0],
        [0.5, -1.0, 0.25],
        comment='; Generated directly from the fixed-band GraphicEQ fitting backend.',
    )

    text = out.read_text()

    assert '; Generated directly from the fixed-band GraphicEQ fitting backend.' in text
    assert 'GraphicEQ: 31.25 1.50; 62.50 -0.50; 125.00 0.00' in text

def test_fit_peq_searches_past_rejected_nearby_candidates_to_use_more_budget():
    freqs = geometric_log_grid()
    target = np.zeros_like(freqs)
    target[freqs <= 120] = 4.0
    target += 6.0 * np.exp(-0.5 * (np.log2(freqs / 2500.0) / 0.32) ** 2)
    target += 5.5 * np.exp(-0.5 * (np.log2(freqs / 4200.0) / 0.32) ** 2)
    target += -5.0 * np.exp(-0.5 * (np.log2(freqs / 8200.0) / 0.28) ** 2)

    bands = fit_peq(freqs, target, sample_rate=48000, max_filters=8)

    assert len(bands) >= 6
    assert sum(1 for band in bands if band.kind == 'peaking') >= 4


def test_fit_peq_budget_of_two_is_fully_spent_by_edge_shelves_before_peaking_filters():
    freqs = geometric_log_grid()
    target = np.zeros_like(freqs)
    target[freqs <= 120] = 4.0
    target[freqs >= 8000] = -3.0
    target += 5.0 * np.exp(-0.5 * (np.log2(freqs / 2500.0) / 0.28) ** 2)

    bands = fit_peq(freqs, target, sample_rate=48000, max_filters=2)

    assert len(bands) == 2
    assert {band.kind for band in bands} == {'lowshelf', 'highshelf'}


def test_fit_peq_exact_n_uses_full_requested_filter_count_and_improves_obvious_multipeak_target():
    freqs = geometric_log_grid()
    target = np.zeros_like(freqs)
    target += 4.8 * np.exp(-0.5 * (np.log2(freqs / 140.0) / 0.30) ** 2)
    target += -5.4 * np.exp(-0.5 * (np.log2(freqs / 1100.0) / 0.24) ** 2)
    target += 5.1 * np.exp(-0.5 * (np.log2(freqs / 4200.0) / 0.22) ** 2)
    target += -4.7 * np.exp(-0.5 * (np.log2(freqs / 8200.0) / 0.26) ** 2)

    bands = fit_peq(freqs, target, sample_rate=48000, budget=FilterBudget(max_filters=4, fill_policy='exact_n'))
    corrected = peq_chain_response_db(freqs, 48000, bands)
    residual_rms = float(np.sqrt(np.mean((target - corrected) ** 2)))

    assert len(bands) == 4
    assert sum(1 for band in bands if band.kind == 'peaking') >= 3
    assert residual_rms < 2.5


def test_fit_peq_keeps_searching_when_top_residual_candidate_is_rejected(monkeypatch):
    freqs = geometric_log_grid()
    target = np.zeros_like(freqs)
    target += 7.0 * np.exp(-0.5 * (np.log2(freqs / 2500.0) / 0.28) ** 2)
    target += -6.0 * np.exp(-0.5 * (np.log2(freqs / 7000.0) / 0.3) ** 2)

    original = fit_peq.__globals__['_nearby_same_sign_band_exists']
    state = {'calls': 0}

    def fake_nearby(bands, candidate):
        if candidate.kind == 'peaking' and state['calls'] < 2:
            state['calls'] += 1
            return True
        return original(bands, candidate)

    monkeypatch.setitem(fit_peq.__globals__, '_nearby_same_sign_band_exists', fake_nearby)
    try:
        bands = fit_peq(freqs, target, sample_rate=48000, max_filters=4)
    finally:
        monkeypatch.setitem(fit_peq.__globals__, '_nearby_same_sign_band_exists', original)

    assert len(bands) == 4
    assert sum(1 for band in bands if band.kind == 'peaking') >= 2
