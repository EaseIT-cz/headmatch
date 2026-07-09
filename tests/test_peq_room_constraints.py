from __future__ import annotations

import numpy as np

from headmatch.peq import fit_peq
from headmatch.signals import geometric_log_grid


def _target_with_peak(center_hz, gain_db, q_octaves=0.15):
    freqs = geometric_log_grid(20, 20000, 48)
    # A narrow +gain bump centred at center_hz (so eq_target wants a cut there).
    bump = gain_db * np.exp(-0.5 * (np.log2(freqs / center_hz) / q_octaves) ** 2)
    eq_target = -bump  # to correct a +gain room mode, EQ must cut
    return freqs, eq_target


def test_no_band_above_max_freq():
    freqs, eq_target = _target_with_peak(2000.0, 6.0)  # feature well above cutoff
    bands = fit_peq(freqs, eq_target, 48000, max_filters=8,
                    max_gain_db=12.0, max_q=12.0, max_freq_hz=300.0)
    assert all(b.freq <= 300.0 + 1e-6 for b in bands)


def test_allows_narrow_low_frequency_cut():
    # A sharp +6 dB mode at 60 Hz: with the default Q cap (2.0) it would be
    # smoothed away; with low_freq_q_cap it should be matched with high Q.
    freqs, eq_target = _target_with_peak(60.0, 6.0, q_octaves=0.12)
    bands = fit_peq(freqs, eq_target, 48000, max_filters=6,
                    max_gain_db=12.0, max_q=12.0, max_freq_hz=300.0,
                    low_freq_q_cap=12.0)
    low_bands = [b for b in bands if b.freq < 120.0 and b.gain_db < 0]
    assert low_bands, "expected a corrective cut below 120 Hz"
    # The low_freq_q_cap raises the Q ceiling from 2.0 to 12.0 for freq<120 Hz.
    # A narrow notch (0.12 octaves) should result in Q > 4.0 (conservative check).
    assert max(b.q for b in low_bands) > 4.0, f"low bands: {[(b.freq, b.q, b.gain_db) for b in low_bands]}"


def test_defaults_unchanged_when_new_args_absent():
    # Regression guard: the default low-frequency Q cap is still 2.0.
    freqs, eq_target = _target_with_peak(60.0, 6.0, q_octaves=0.12)
    bands = fit_peq(freqs, eq_target, 48000, max_filters=6)
    low_bands = [b for b in bands if b.freq < 120.0]
    assert all(b.q <= 2.0 + 1e-6 for b in low_bands)


def test_asymmetric_boost_cap_survives_joint_refinement():
    # Several deep nulls would each "want" a large boost; max_boost_db must bound
    # every returned band's gain even after joint Nelder-Mead refinement runs.
    freqs = geometric_log_grid(20, 20000, 48)
    eq_target = (8.0 * np.exp(-0.5 * (np.log2(freqs / 60.0) / 0.12) ** 2)
                 + 8.0 * np.exp(-0.5 * (np.log2(freqs / 90.0) / 0.12) ** 2))  # wants +8 dB boosts
    bands = fit_peq(freqs, eq_target, 48000, max_filters=6,
                    max_gain_db=12.0, max_q=8.0, max_freq_hz=300.0,
                    low_freq_q_cap=8.0, max_boost_db=2.0)
    assert bands, "expected bands"
    assert all(b.gain_db <= 2.0 + 1e-6 for b in bands)
    # Cuts are still allowed to go well below the boost ceiling.
    assert any(b.gain_db < -2.0 for b in fit_peq(
        freqs, -eq_target, 48000, max_filters=6, max_gain_db=12.0,
        max_q=8.0, max_freq_hz=300.0, low_freq_q_cap=8.0, max_boost_db=2.0))


def test_shelf_boost_respects_max_boost_db():
    # A broad low-frequency deficit produces a low-shelf *boost* candidate.
    # Shelves must honour max_boost_db just like peaking bands, otherwise room
    # correction can emit an 8-12 dB shelf boost past the documented ceiling.
    freqs = geometric_log_grid(20, 20000, 48)
    eq_target = np.where(freqs <= 140.0, 8.0, 0.0)  # wants +8 dB in the bass
    bands = fit_peq(freqs, eq_target, 48000, max_filters=6,
                    max_gain_db=12.0, max_q=8.0, max_freq_hz=300.0,
                    low_freq_q_cap=8.0, max_boost_db=2.0)
    shelves = [b for b in bands if b.kind == 'lowshelf']
    assert shelves, "expected a low-shelf boost candidate"
    assert all(b.gain_db <= 2.0 + 1e-6 for b in bands), \
        f"shelf/peak boost exceeded ceiling: {[(b.kind, b.gain_db) for b in bands]}"


def test_default_low_freq_q_cap_holds_after_joint_refinement():
    # Regression guard (design contract): on the default path (no low_freq_q_cap)
    # the 2.0 Q ceiling below 120 Hz must hold on the RETURNED bands, i.e. even
    # after joint Nelder-Mead refinement. Two narrow low modes force >=2 peaking
    # bands so the refinement pass actually runs.
    freqs = geometric_log_grid(20, 20000, 48)
    eq_target = -(6.0 * np.exp(-0.5 * (np.log2(freqs / 45.0) / 0.12) ** 2)
                  + 6.0 * np.exp(-0.5 * (np.log2(freqs / 80.0) / 0.12) ** 2))
    bands = fit_peq(freqs, eq_target, 48000, max_filters=6, max_q=4.5)
    low_bands = [b for b in bands if b.freq < 120.0]
    assert len(low_bands) >= 2, "expected the refinement path to be exercised"
    assert all(b.q <= 2.0 + 1e-6 for b in low_bands), \
        f"low-freq Q exceeded default cap after refinement: {[(b.freq, b.q) for b in low_bands]}"