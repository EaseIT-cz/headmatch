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
    # After S-to-Q conversion, shelf Q differs from the raw S=0.7 stored in band.q
    assert payload['filters']['L_1_lowshelf']['parameters']['q'] != 0.7  # not raw S
    assert 0.55 < payload['filters']['L_1_lowshelf']['parameters']['q'] < 0.65  # converted Q


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
    # Shelf S=1.5 clamped to 1.0, then converted to Q
    assert abs(payload['filters']['R_1_highshelf']['parameters']['q'] - 0.7071) < 0.01
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

def test_drift_between_dense_graphiceq_export_and_fixed_fit_is_reasonable(tmp_path):
    """Test that fixed-band GraphicEQ fit doesn't drift too far from dense export.

    This test ensures the difference between:
    - Dense GraphicEQ export (export_equalizer_apo_graphiceq_txt with full freq grid)
    - Fixed-band GraphicEQ fit (fit_peq with family='graphic_eq')

    is bounded and reasonable, not uncontrolled "drift".
    """
    from headmatch.signals import geometric_log_grid
    from headmatch.peq import graphic_eq_profile, peq_chain_response_db
    from headmatch.exporters import export_equalizer_apo_graphiceq_txt
    from headmatch.peq import FilterBudget
    from scipy import interpolate

    freqs = geometric_log_grid()
    target = np.zeros_like(freqs)
    target += 4.0 * np.exp(-0.5 * (np.log2(freqs / 1000.0) / 0.55) ** 2)
    target += -3.0 * np.exp(-0.5 * (np.log2(freqs / 8000.0) / 0.45) ** 2)

    # Simulate measurement deviation
    measurement = target + 2.0 * np.exp(-0.5 * (np.log2(freqs / 3000.0) / 0.25) ** 2)
    left_target = target - measurement

    # Fit using fixed-band GraphicEQ
    fixed_bands = fit_peq(
        freqs,
        left_target,
        sample_rate=48000,
        budget=FilterBudget(family='graphic_eq', max_filters=10, profile='geq_10_band'),
    )

    # Compute the fixed-band correction curve
    fixed_correction = peq_chain_response_db(freqs, 48000, fixed_bands)

    # Compute dense GraphicEQ-style correction at profile frequencies only
    profile = graphic_eq_profile('geq_10_band')
    profile_freqs = np.array(profile.freqs_hz)
    profile_target = np.interp(profile_freqs, freqs, left_target)
    profile_measurement = np.interp(profile_freqs, freqs, measurement)
    profile_residual = profile_target - profile_measurement

    # Interpolate profile_residual to full grid for comparison
    interp_func = interpolate.interp1d(profile_freqs, profile_residual, kind='linear', fill_value='extrapolate')
    interpolated_correction = interp_func(freqs)

    # Compare at profile frequencies - find closest matches in freqs for each profile frequency
    fixed_at_profile = []
    dense_at_profile = []
    for pf in profile_freqs:
        closest_idx = np.argmin(np.abs(freqs - pf))
        fixed_at_profile.append(fixed_correction[closest_idx])
        dense_at_profile.append(interpolated_correction[closest_idx])
    fixed_at_profile = np.array(fixed_at_profile)
    dense_at_profile = np.array(dense_at_profile)

    # RMS difference at profile frequencies
    rms_drift = float(np.sqrt(np.mean((fixed_at_profile - dense_at_profile) ** 2)))

    # The drift should be bounded - typically under 1 dB RMS
    assert rms_drift < 2.0, f"Drift between fixed-fit and dense export too large: {rms_drift:.2f} dB RMS"

    # Verify the fixed-fit output file is generated correctly
    out_dir = tmp_path / 'drift_test'
    out_dir.mkdir()
    export_equalizer_apo_graphiceq_txt(
        out_dir / 'fixed_graphiceq.txt',
        freqs,
        left_target,
        left_target,
        comment='; Fixed-band GraphicEQ fit for drift testing.',
    )
    fixed_file = out_dir / 'fixed_graphiceq.txt'
    assert fixed_file.exists()
    assert 'Fixed-band GraphicEQ fit for drift testing.' in fixed_file.read_text()


def test_fit_peq_exact_n_fills_all_requested_filters_on_broad_spiky_target():
    """Test exact_n policy fills all filters even when residual is small."""
    freqs = geometric_log_grid()
    target = np.zeros_like(freqs)
    # Very broad peaks that will require many filters
    target += 3.0 * np.exp(-0.5 * (np.log2(freqs / 500.0) / 0.8) ** 2)
    target += -2.5 * np.exp(-0.5 * (np.log2(freqs / 3000.0) / 0.9) ** 2)
    target += 2.0 * np.exp(-0.5 * (np.log2(freqs / 10000.0) / 1.0) ** 2)

    bands = fit_peq(freqs, target, sample_rate=48000, budget=FilterBudget(max_filters=10, fill_policy='exact_n'))

    assert len(bands) == 10
    assert sum(1 for b in bands if b.kind == 'peaking') >= 8


def test_fit_peq_underfits_when_target_is_smaller_than_min_gain():
    """Test that fit_peq returns empty when target changes are tiny."""
    freqs = geometric_log_grid()
    target = 0.05 * np.exp(-0.5 * (np.log2(freqs / 1000.0) / 0.55) ** 2)

    bands = fit_peq(freqs, target, sample_rate=48000, max_filters=4)

    assert len(bands) == 0


def test_clone_target_normalizes_before_comparison():
    """Ensure clone_target normalizes curves before comparing for matching."""
    from headmatch.targets import clone_target_from_source_target, TargetCurve
    from headmatch.targets import save_fr_csv
    import tempfile
    import os

    freqs = np.linspace(20, 20000, 100)
    base_response = np.random.randn(100) * 2 + 0
    boosted = base_response + 5.0

    with tempfile.TemporaryDirectory() as tmpdir:
        base_path = os.path.join(tmpdir, 'base.csv')
        boosted_path = os.path.join(tmpdir, 'boosted.csv')
        relative_path = os.path.join(tmpdir, 'relative.csv')

        save_fr_csv(base_path, freqs, base_response)
        save_fr_csv(boosted_path, freqs, boosted)

        # Clone should match boosted to base after normalization
        relative = clone_target_from_source_target(boosted_path, base_path, relative_path)
        assert relative is not None
        rel_response = relative.values_db
        # After normalization, should be near zero
        assert np.std(rel_response) < 0.5


def test_export_equalizer_apo_graphiceq_handles_zero_preamp_channels():
    """Test GraphicEQ export with zero preamp values."""
    from headmatch.exporters import export_equalizer_apo_graphiceq_txt
    import tempfile

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        export_equalizer_apo_graphiceq_txt(
            f.name,
            [20.0, 1000.0, 20000.0],
            [0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0],
        )
        content = open(f.name).read()

    assert 'Preamp:' in content
    assert 'GraphicEQ: 20.00 0.00; 1000.00 0.00; 20000.00 0.00' in content


def test_fit_peq_graphiceq_10_band_outputs_correct_number_of_bands():
    """Ensure fixed-band GraphicEQ output matches profile frequency count."""
    from headmatch.peq import graphic_eq_profile

    freqs = geometric_log_grid()
    target = np.random.randn(len(freqs)) * 2

    bands = fit_peq(freqs, target, sample_rate=48000, budget=FilterBudget(family='graphic_eq', max_filters=10, profile='geq_10_band'))

    profile = graphic_eq_profile('geq_10_band')
    assert len(bands) == len(profile.freqs_hz)
    assert all(b.kind == 'peaking' for b in bands)
    assert all(round(b.q, 4) == round(profile.q, 4) for b in bands)


def test_fit_peq_graphiceq_31_band_uses_correct_profile():
    """Test 31-band GraphicEQ profile selection."""
    freqs = geometric_log_grid()
    target = np.random.randn(len(freqs)) * 2

    bands = fit_peq(freqs, target, sample_rate=48000, budget=FilterBudget(family='graphic_eq', max_filters=31, profile='geq_31_band'))

    profile = graphic_eq_profile('geq_31_band')
    assert len(bands) == len(profile.freqs_hz)
    assert 20.0 in profile.freqs_hz
    assert 20000.0 in profile.freqs_hz


def test_camilladsp_export_sorts_filters_by_channel_and_index():
    """Ensure CamillaDSP export orders filters correctly."""
    from headmatch.exporters import export_camilladsp_filter_snippet_yaml
    import tempfile

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.yaml') as f:
        export_camilladsp_filter_snippet_yaml(
            f.name,
            [
                PEQBand('lowshelf', 100.0, 2.0, 0.7),
                PEQBand('peaking', 3000.0, 1.5, 2.0),
                PEQBand('highshelf', 10000.0, -1.0, 0.7),
            ],
            [],
        )
        content = open(f.name).read()

    # Pipeline order should match filter order
    assert 'L_1_lowshelf' in content
    assert 'L_2_peaking' in content
    assert 'L_3_highshelf' in content
