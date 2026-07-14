"""Coverage tests for pipeline.py thin wrappers / branches and
pipeline_confidence.py's alignment-peak warning line.

New tests only; existing test files are untouched.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from headmatch.analysis import MeasurementResult
from headmatch.contracts import ConfidenceSummary
from headmatch.hearing_test import (
    NORMAL_HEARING_REFERENCE,
    TEST_FREQUENCIES,
    FrequencyThreshold,
    HearingProfile,
)
from headmatch.peq import FilterBudget
from headmatch import pipeline
from headmatch.pipeline import (
    ResolvedTargetCurves,
    _hearing_run_summary,
    _metrics,
    _resolve_target_curves,
    _summarize_trustworthiness,
    _write_fit_artifacts,
    build_clone_curve,
)
from headmatch.pipeline_confidence import summarize_trustworthiness
from headmatch.targets import TargetCurve


def _clean_diagnostics(**overrides) -> dict:
    diag = {
        'alignment_reference_score': 0.99,
        'alignment_peak_ratio': 0.99,
        'channel_mismatch_rms_db': 0.1,
        'left_roughness_db': 0.1,
        'right_roughness_db': 0.1,
        'capture_rms_dbfs': -20.0,
    }
    diag.update(overrides)
    return diag


def _result(diagnostics: dict | None = None) -> MeasurementResult:
    freqs = np.array([20.0, 1000.0, 20000.0])
    return MeasurementResult(
        freqs_hz=freqs,
        left_db=np.array([1.0, 0.0, -1.0]),
        right_db=np.array([2.0, 0.0, -2.0]),
        left_raw_db=np.array([1.0, 0.0, -1.0]),
        right_raw_db=np.array([2.0, 0.0, -2.0]),
        diagnostics=diagnostics if diagnostics is not None else _clean_diagnostics(),
    )


def _clean_report() -> dict:
    return {
        'predicted_left_rms_error_db': 0.1,
        'predicted_right_rms_error_db': 0.1,
        'predicted_left_max_error_db': 0.2,
        'predicted_right_max_error_db': 0.2,
    }


class TestResolvedTargetCurvesProperties:
    def test_name_and_semantics_delegate_to_base(self):
        result = _result()
        target = TargetCurve(result.freqs_hz, np.zeros_like(result.freqs_hz), 'mytarget', semantics='relative')
        resolved = _resolve_target_curves(result, target)
        assert isinstance(resolved, ResolvedTargetCurves)
        # lines 63 and 67
        assert resolved.name == 'mytarget'
        assert resolved.semantics == 'relative'


class TestThinWrappers:
    def test_summarize_trustworthiness_wrapper_matches_direct_call(self):
        result = _result()
        report = _clean_report()
        # line 88
        wrapped = _summarize_trustworthiness(result, report)
        direct = summarize_trustworthiness(result, report)
        assert wrapped.to_dict() == direct.to_dict()

    def test_write_fit_artifacts_wrapper_delegates(self, monkeypatch):
        captured = {}

        def fake_write(out_dir, **kwargs):
            captured['out_dir'] = out_dir
            captured.update(kwargs)
            return {'ok': True}

        monkeypatch.setattr('headmatch.pipeline.write_fit_artifacts', fake_write)
        # line 94
        out = _write_fit_artifacts(
            Path('somewhere'),
            kind='fit',
            result='r',
            target='t',
            left_bands=[],
            right_bands=[],
            report={},
            sample_rate=48000,
            write_target_curve_csv=True,
            filter_budget=FilterBudget(max_filters=4),
        )
        assert out == {'ok': True}
        assert captured['kind'] == 'fit'
        assert captured['sample_rate'] == 48000

    def test_build_clone_curve_wrapper_delegates(self, monkeypatch):
        sentinel = object()

        def fake_clone(source, target, out):
            assert (source, target, out) == ('s', 't', 'o')
            return sentinel

        monkeypatch.setattr('headmatch.pipeline.clone_target_from_source_target', fake_clone)
        # line 187
        assert build_clone_curve('s', 't', 'o') is sentinel


class TestMetricsBandFallback:
    def test_metrics_falls_back_to_full_range_when_no_audible_points(self):
        # All frequencies fall outside the 80-12000 Hz band -> mask empty,
        # so the fallback full mask is used (line 109).
        freqs = np.array([20.0, 40.0, 60.0])
        measured = np.array([1.0, 2.0, 3.0])
        target = np.array([0.0, 0.0, 0.0])
        rms, max_abs = _metrics(freqs, measured, target)
        expected_rms = float(np.sqrt(np.mean(measured ** 2)))
        assert rms == pytest.approx(expected_rms)
        assert max_abs == pytest.approx(3.0)


class TestConfidenceAlignmentPeakWarning:
    def test_low_alignment_peak_ratio_emits_warning(self):
        # alignment_peak_ratio below ALIGNMENT_PEAK_WARNING_THRESHOLD (0.85)
        # triggers the warning on line 82 of pipeline_confidence.
        diag = _clean_diagnostics(alignment_peak_ratio=0.50)
        result = _result(diag)
        summary = summarize_trustworthiness(result, _clean_report())
        assert any('alignment peak' in w for w in summary.warnings)

    def test_room_confidence_uses_room_specific_language(self):
        diag = _clean_diagnostics(
            channel_mismatch_rms_db=3.0,
            left_roughness_db=2.0,
            right_roughness_db=2.0,
        )
        summary = summarize_trustworthiness(_result(diag), _clean_report(), workflow="room")
        text = " ".join((summary.interpretation, *summary.warnings)).lower()

        assert "room" in text
        assert "headset" not in text
        assert "headphones" not in text
        assert "leaky seal" not in text


def _profile_with(left_thresholds, right_thresholds) -> HearingProfile:
    return HearingProfile(
        left=left_thresholds,
        right=right_thresholds,
        tested_at='2026-01-01T00:00:00+00:00',
        asymmetric_freqs=[],
    )


def _threshold(freq, *, determined=True, floored=False) -> FrequencyThreshold:
    return FrequencyThreshold(
        freq_hz=freq,
        level_dbfs=NORMAL_HEARING_REFERENCE[freq],
        ascending_runs=3,
        determined=determined,
        floored=floored,
    )


class TestConfidenceScoringPinnedValues:
    """Pin the current confidence-scoring constants and computed scores.

    These tests detect drift between documentation and implementation.
    If any pinned value changes, the test fails to signal a docs update is needed.
    """

    def test_weights_sum_to_100(self):
        from headmatch.pipeline_confidence import (
            ALIGNMENT_WEIGHT,
            ALIGNMENT_PEAK_WEIGHT,
            CHANNEL_MISMATCH_WEIGHT,
            ROUGHNESS_WEIGHT,
            RESIDUAL_RMS_WEIGHT,
            RESIDUAL_PEAK_WEIGHT,
        )
        total = (
            ALIGNMENT_WEIGHT
            + ALIGNMENT_PEAK_WEIGHT
            + CHANNEL_MISMATCH_WEIGHT
            + ROUGHNESS_WEIGHT
            + RESIDUAL_RMS_WEIGHT
            + RESIDUAL_PEAK_WEIGHT
        )
        assert total == 100

    def test_threshold_values_pinned(self):
        from headmatch.pipeline_confidence import (
            ALIGNMENT_SCORE_WARN,
            ALIGNMENT_SCORE_SEVERE,
            CHANNEL_MISMATCH_WARN_DB,
            CHANNEL_MISMATCH_SEVERE_DB,
            SCORE_HIGH_THRESHOLD,
            SCORE_MEDIUM_THRESHOLD,
        )
        assert ALIGNMENT_SCORE_WARN == 0.20
        assert ALIGNMENT_SCORE_SEVERE == 0.40
        assert CHANNEL_MISMATCH_WARN_DB == 0.8
        assert CHANNEL_MISMATCH_SEVERE_DB == 2.5
        assert SCORE_HIGH_THRESHOLD == 85
        assert SCORE_MEDIUM_THRESHOLD == 65

    def test_clean_measurement_score_is_100_label_high(self):
        result = _result(_clean_diagnostics())
        summary = summarize_trustworthiness(result, _clean_report())
        assert summary.score == 100
        assert summary.label == 'high'

    def test_worst_case_measurement_score_is_0_label_low(self):
        diag = _clean_diagnostics(
            alignment_reference_score=0.50,  # Below ALIGNMENT_SCORE_SEVERE
            alignment_peak_ratio=0.50,  # Below ALIGNMENT_PEAK_SEVERE (1-0.35=0.65)
            channel_mismatch_rms_db=3.0,  # Above CHANNEL_MISMATCH_SEVERE_DB
            left_roughness_db=2.0,  # Above ROUGHNESS_SEVERE_DB
            right_roughness_db=2.0,
        )
        result = _result(diag)
        report = _clean_report()
        report['predicted_left_rms_error_db'] = 5.0  # Above RESIDUAL_RMS_SEVERE_DB
        report['predicted_right_rms_error_db'] = 5.0
        report['predicted_left_max_error_db'] = 10.0  # Above RESIDUAL_PEAK_SEVERE_DB
        report['predicted_right_max_error_db'] = 10.0
        summary = summarize_trustworthiness(result, report)
        assert summary.score == 0
        assert summary.label == 'low'

    def test_medium_boundary_label_at_threshold(self):
        from headmatch.pipeline_confidence import (
            CHANNEL_MISMATCH_WEIGHT,
            CHANNEL_MISMATCH_WARN_DB,
            CHANNEL_MISMATCH_SEVERE_DB,
            SCORE_MEDIUM_THRESHOLD,
            _confidence_penalty,
        )
        # Target: score == SCORE_MEDIUM_THRESHOLD (65)
        # Score = 100 - total_penalty, so need penalty = 35.
        # Use channel_mismatch penalty only, set others to zero.
        # penalty = _confidence_penalty(value, warn, severe) * CHANNEL_MISMATCH_WEIGHT
        # For penalty = 35 / 36 ≈ 0.9722, we need:
        #   (value - warn) / (severe - warn) ≈ 0.9722
        # value = warn + 0.9722 * (severe - warn)
        target_penalty = 100 - SCORE_MEDIUM_THRESHOLD
        normalized = target_penalty / CHANNEL_MISMATCH_WEIGHT
        value = CHANNEL_MISMATCH_WARN_DB + normalized * (
            CHANNEL_MISMATCH_SEVERE_DB - CHANNEL_MISMATCH_WARN_DB
        )
        # Keep all other metrics perfect (clean diagnostics)
        diag = _clean_diagnostics(
            channel_mismatch_rms_db=value,
        )
        result = _result(diag)
        summary = summarize_trustworthiness(result, _clean_report())
        assert summary.label == 'medium'


class TestHearingRunSummaryConfidenceBranches:
    """Exercise the floored / medium / few-converged branches (lines 417, 420-423)."""

    def _confidence(self, profile):
        report = {
            'predicted_left_rms_error_db': 0.1,
            'predicted_right_rms_error_db': 0.1,
            'predicted_left_max_error_db': 0.2,
            'predicted_right_max_error_db': 0.2,
            'target': 'flat',
            'eq_clipping': None,
        }
        summary = _hearing_run_summary(
            profile, Path('out'), [], [], report, 48000, FilterBudget(max_filters=4)
        )
        return summary.to_dict()['confidence']

    def test_floored_frequencies_score_low(self):
        # At least one floored threshold -> line 417 (label "low", score 30).
        side = {f: _threshold(f, determined=True) for f in TEST_FREQUENCIES}
        first = TEST_FREQUENCIES[0]
        side[first] = _threshold(first, determined=True, floored=True)
        profile = _profile_with(dict(side), dict(side))
        confidence = self._confidence(profile)
        assert confidence['label'] == 'low'
        assert confidence['score'] == 30
        assert 'floored' in confidence['headline'].lower()

    def test_all_determined_scores_high(self):
        # determined == total -> line 419 (label "high").
        side = {f: _threshold(f, determined=True) for f in TEST_FREQUENCIES}
        profile = _profile_with(dict(side), dict(side))
        confidence = self._confidence(profile)
        assert confidence['label'] == 'high'
        assert confidence['score'] == 80

    def test_most_determined_scores_medium(self):
        # >= 60% but < 100% determined, none floored -> lines 420-421 (medium, 60).
        freqs = list(TEST_FREQUENCIES)
        n = len(freqs)
        # Make exactly enough determined to clear the 60% bar but not all.
        n_determined = max(int(np.ceil(0.6 * n)), 1)
        n_determined = min(n_determined, n - 1)  # ensure strictly below total
        side = {}
        for i, f in enumerate(freqs):
            side[f] = _threshold(f, determined=(i < n_determined))
        profile = _profile_with(dict(side), dict(side))
        confidence = self._confidence(profile)
        assert confidence['label'] == 'medium'
        assert confidence['score'] == 60

    def test_few_determined_scores_low(self):
        # < 60% determined, none floored -> lines 422-423 (low, 40).
        side = {f: _threshold(f, determined=False) for f in TEST_FREQUENCIES}
        profile = _profile_with(dict(side), dict(side))
        confidence = self._confidence(profile)
        assert confidence['label'] == 'low'
        assert confidence['score'] == 40
        assert 'uncertain' in confidence['headline'].lower()
