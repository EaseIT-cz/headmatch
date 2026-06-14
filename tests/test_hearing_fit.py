"""Tests for the equipment-free hearing-fit pipeline."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from headmatch.hearing_test import (
    NORMAL_HEARING_REFERENCE,
    TEST_FREQUENCIES,
    FrequencyThreshold,
    HearingProfile,
)
from headmatch.pipeline import fit_from_hearing_profile, run_hearing_fit


def _make_profile(loss_db: float = 0.0) -> HearingProfile:
    side = {
        f: FrequencyThreshold(
            freq_hz=f,
            level_dbfs=NORMAL_HEARING_REFERENCE[f] + loss_db,
            ascending_runs=3,
            determined=True,
        )
        for f in TEST_FREQUENCIES
    }
    return HearingProfile(
        left=dict(side),
        right=dict(side),
        tested_at="2026-01-01T00:00:00+00:00",
        asymmetric_freqs=[],
    )


def _sloping_profile() -> HearingProfile:
    # Progressively worse than 1 kHz at high frequency, beyond the normal shape ->
    # a relative high-frequency deviation that should be compensated.
    levels = {500: -60, 1000: -60, 2000: -58, 3000: -52, 4000: -46, 6000: -40, 8000: -34}
    side = {f: FrequencyThreshold(f, levels[f], 3, True) for f in TEST_FREQUENCIES}
    return HearingProfile(left=dict(side), right=dict(side), tested_at="t", asymmetric_freqs=[])


class TestFitFromHearingProfile:
    def test_returns_band_lists_and_report(self):
        profile = _make_profile(loss_db=10.0)
        left_bands, right_bands, report = fit_from_hearing_profile(
            profile, sample_rate=48000, max_filters=4
        )
        assert isinstance(left_bands, list)
        assert isinstance(right_bands, list)
        assert isinstance(report, dict)

    def test_mode_is_hearing_only(self):
        profile = _make_profile()
        _, _, report = fit_from_hearing_profile(profile, sample_rate=48000, max_filters=4)
        assert report["mode"] == "hearing_only"

    def test_compensation_flag_set(self):
        profile = _make_profile()
        _, _, report = fit_from_hearing_profile(profile, sample_rate=48000, max_filters=4)
        assert report["hearing_compensation_applied"] is True

    def test_report_has_predicted_error(self):
        profile = _make_profile(loss_db=10.0)
        _, _, report = fit_from_hearing_profile(profile, sample_rate=48000, max_filters=4)
        assert "predicted_left_rms_error_db" in report
        assert "predicted_right_rms_error_db" in report
        assert isinstance(report["predicted_left_rms_error_db"], float)

    def test_report_has_eq_clipping(self):
        profile = _make_profile(loss_db=10.0)
        _, _, report = fit_from_hearing_profile(profile, sample_rate=48000, max_filters=4)
        assert "eq_clipping" in report
        assert "will_clip" in report["eq_clipping"]

    def test_report_has_hearing_profile_summary(self):
        profile = _make_profile()
        _, _, report = fit_from_hearing_profile(profile, sample_rate=48000, max_filters=4)
        assert "hearing_profile_summary" in report
        assert report["hearing_profile_summary"]["tested_at"] == "2026-01-01T00:00:00+00:00"

    def test_normal_hearing_gives_small_boost(self):
        """Normal hearing → near-zero compensation → near-flat EQ with flat target."""
        from headmatch.peq import peq_chain_response_db
        from headmatch.signals import geometric_log_grid
        profile = _make_profile(loss_db=0.0)
        left_bands, _, _ = fit_from_hearing_profile(profile, sample_rate=48000, max_filters=8)
        grid = geometric_log_grid(200.0, 8000.0, 48)
        resp = peq_chain_response_db(grid, 48000, left_bands)
        assert float(np.max(np.abs(resp))) < 2.0  # very near flat

    def test_sloping_hf_loss_produces_hf_boost(self):
        """A sloping HF deviation (worse than normal at high freq, relative to the
        listener's own 1 kHz) produces a positive high-frequency boost."""
        from headmatch.peq import peq_chain_response_db
        from headmatch.signals import geometric_log_grid
        left_bands, _, _ = fit_from_hearing_profile(_sloping_profile(), sample_rate=48000, max_filters=8)
        assert left_bands
        grid = geometric_log_grid(2000.0, 8000.0, 48)
        resp = peq_chain_response_db(grid, 48000, left_bands)
        assert float(np.mean(resp)) > 1.0

    def test_symmetric_left_right_bands(self):
        """Symmetric hearing profile → left and right bands identical."""
        left_bands, right_bands, _ = fit_from_hearing_profile(
            _sloping_profile(), sample_rate=48000, max_filters=4
        )
        assert left_bands and len(left_bands) == len(right_bands)
        for lb, rb in zip(left_bands, right_bands):
            assert lb.freq == pytest.approx(rb.freq, abs=0.1)
            assert lb.gain_db == pytest.approx(rb.gain_db, abs=0.01)

    def test_with_target_csv(self, tmp_path):
        """Passing a target CSV path is accepted and runs without error."""
        csv = tmp_path / "target.csv"
        csv.write_text("frequency_hz,response_db\n20,0\n1000,0\n20000,0\n", encoding="utf-8")
        profile = _make_profile(loss_db=10.0)
        left_bands, _, report = fit_from_hearing_profile(
            profile, sample_rate=48000, max_filters=4, target_path=csv
        )
        assert isinstance(left_bands, list)
        assert isinstance(report["target"], str)

    def test_target_curve_applied_even_with_no_hearing_loss(self, tmp_path):
        # Regression: a tonal target (e.g. Harman) must still produce an EQ when
        # the listener shows no measurable hearing loss — the target is known
        # independently of the hearing test.
        from headmatch.builtin_targets import materialize_builtin_target
        # Thresholds exactly at the reference -> zero compensation.
        side = {
            f: FrequencyThreshold(f, NORMAL_HEARING_REFERENCE[f], 3, True)
            for f in TEST_FREQUENCIES
        }
        profile = HearingProfile(left=dict(side), right=dict(side), tested_at="t", asymmetric_freqs=[])
        harman = materialize_builtin_target("harman", tmp_path)
        left_bands, _, _ = fit_from_hearing_profile(profile, sample_rate=48000, target_path=harman)
        assert left_bands, "Harman target should yield EQ bands even with no hearing loss"

    def test_filter_budget_respected(self):
        from headmatch.peq import FilterBudget
        profile = _make_profile(loss_db=20.0)
        budget = FilterBudget(max_filters=2, fill_policy="exact_n")
        left_bands, right_bands, _ = fit_from_hearing_profile(
            profile, sample_rate=48000, max_filters=2, filter_budget=budget
        )
        assert len(left_bands) <= 2
        assert len(right_bands) <= 2


class TestRunHearingFit:
    def _profile(self, loss_db: float = 10.0) -> HearingProfile:
        return _make_profile(loss_db=loss_db)

    def test_writes_all_expected_files(self, tmp_path):
        profile = self._profile()
        run_hearing_fit(profile, tmp_path, sample_rate=48000)
        assert (tmp_path / "equalizer_apo.txt").exists()
        assert (tmp_path / "equalizer_apo_graphiceq.txt").exists()
        assert (tmp_path / "camilladsp_full.yaml").exists()
        assert (tmp_path / "camilladsp_filters_only.yaml").exists()
        assert (tmp_path / "hearing_fit_report.json").exists()
        assert (tmp_path / "README.txt").exists()

    def test_writes_profile_copy_to_results_dir(self, tmp_path):
        profile = self._profile(loss_db=20.0)
        run_hearing_fit(profile, tmp_path, sample_rate=48000)
        prof_path = tmp_path / "hearing_profile.json"
        assert prof_path.exists()
        data = json.loads(prof_path.read_text(encoding="utf-8"))
        assert set(data["left"]) == {str(f) for f in TEST_FREQUENCIES}
        assert data["tested_at"] == profile.tested_at

    def test_left_channel_not_attenuated_when_only_right_has_boost(self, tmp_path):
        # A channel with no boost must not get a preamp (no L/R imbalance).
        from headmatch.hearing_test import NORMAL_RELATIVE_SHAPE_DB
        left = {f: FrequencyThreshold(f, -60.0 + NORMAL_RELATIVE_SHAPE_DB[f], 3, True) for f in TEST_FREQUENCIES}
        right_levels = {500: -60, 1000: -60, 2000: -58, 3000: -52, 4000: -46, 6000: -40, 8000: -34}
        right = {f: FrequencyThreshold(f, right_levels[f], 3, True) for f in TEST_FREQUENCIES}
        profile = HearingProfile(left=left, right=right, tested_at="t", asymmetric_freqs=[])
        run_hearing_fit(profile, tmp_path, sample_rate=48000)

        apo = (tmp_path / "equalizer_apo.txt").read_text()
        left_section = apo.split("Channel: R")[0]
        assert "Channel: L" in left_section
        assert "Preamp: 0.00 dB" in left_section  # no boost -> no attenuation
        assert "Filter" not in left_section

    def test_report_json_valid(self, tmp_path):
        profile = self._profile()
        run_hearing_fit(profile, tmp_path, sample_rate=48000)
        data = json.loads((tmp_path / "hearing_fit_report.json").read_text(encoding="utf-8"))
        assert data["mode"] == "hearing_only"
        assert data["hearing_compensation_applied"] is True
        assert "left_bands" in data
        assert "right_bands" in data
        assert "eq_clipping" in data

    def test_writes_run_summary_discoverable_in_history(self, tmp_path):
        from headmatch.ab_compare import load_run_summary
        from headmatch.history import load_recent_runs
        out = tmp_path / "run"
        run_hearing_fit(self._profile(loss_db=20.0), out, sample_rate=48000)
        assert (out / "run_summary.json").exists()
        summary = load_run_summary(out)  # parses cleanly
        assert summary.kind in ("fit", "iteration")
        assert any(r.summary_path.parent == out for r in load_recent_runs(tmp_path))

    def test_returns_report_dict(self, tmp_path):
        profile = self._profile()
        result = run_hearing_fit(profile, tmp_path, sample_rate=48000)
        assert isinstance(result, dict)
        assert "mode" in result

    def test_creates_output_dir(self, tmp_path):
        profile = self._profile()
        out = tmp_path / "nested" / "hearing_fit"
        run_hearing_fit(profile, out, sample_rate=48000)
        assert out.is_dir()
        assert (out / "equalizer_apo.txt").exists()

    def test_readme_contains_key_info(self, tmp_path):
        profile = self._profile(loss_db=20.0)
        run_hearing_fit(profile, tmp_path, sample_rate=48000)
        readme = (tmp_path / "README.txt").read_text(encoding="utf-8")
        assert "hearing_only" in readme or "hearing-fit" in readme or "hearing profile" in readme.lower()
        assert "equalizer_apo.txt" in readme

    def test_with_target_csv(self, tmp_path):
        csv = tmp_path / "target.csv"
        csv.write_text("frequency_hz,response_db\n20,0\n1000,0\n20000,0\n", encoding="utf-8")
        out = tmp_path / "fit"
        profile = self._profile()
        run_hearing_fit(profile, out, sample_rate=48000, target_path=csv)
        assert (out / "equalizer_apo.txt").exists()

    def test_equalizer_apo_parametric_format(self, tmp_path):
        profile = self._profile(loss_db=15.0)
        run_hearing_fit(profile, tmp_path, sample_rate=48000)
        content = (tmp_path / "equalizer_apo.txt").read_text(encoding="utf-8")
        assert "Filter" in content or "Preamp" in content


class TestFitFromHearingProfileRelativeTarget:
    """Cover the 'relative' semantics branch in fit_from_hearing_profile."""

    def test_relative_semantics_target_csv(self, tmp_path):
        csv = tmp_path / "clone_something_to_other.csv"
        csv.write_text(
            "# headmatch_target_semantics=relative\nfrequency_hz,response_db\n20,0\n1000,0\n20000,0\n",
            encoding="utf-8",
        )
        side = {
            f: FrequencyThreshold(
                freq_hz=f,
                level_dbfs=NORMAL_HEARING_REFERENCE[f] + 10.0,
                ascending_runs=3,
                determined=True,
            )
            for f in TEST_FREQUENCIES
        }
        profile = HearingProfile(
            left=dict(side), right=dict(side),
            tested_at="2026-01-01T00:00:00+00:00",
            asymmetric_freqs=[],
        )
        left_bands, right_bands, report = fit_from_hearing_profile(
            profile, sample_rate=48000, max_filters=4, target_path=csv
        )
        assert isinstance(left_bands, list)
        assert report["hearing_compensation_applied"] is True
