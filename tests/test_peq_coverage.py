"""Coverage tests for headmatch.peq defensive/edge branches."""
from __future__ import annotations

import dataclasses

import numpy as np
import pytest

import headmatch.peq as peq
from headmatch.peq import (
    FilterBudget,
    FitObjective,
    PEQBand,
    _band_mean,
    _default_graphic_eq_profile_name,
    _edge_shelf_candidate,
    _refine_bands_jointly,
    _same_sign_fraction,
    _select_peaking_candidate,
    biquad_response_db,
    fit_peq,
    graphic_eq_profile,
    solve_band_gains_lsq,
)


class TestShelfQNonPositiveInner:
    def test_shelf_q_returns_default_when_inner_non_positive(self, monkeypatch):
        """PEQBand.shelf_q returns 0.707 when the RBJ inner term is <= 0 (line 125).

        ``effective_slope`` is clamped to [0.1, 1.0] via ``min``/``max`` builtins,
        which keeps the inner term >= 2. We shadow the module-level ``min`` so the
        clamp is defeated and the slope can exceed 1.0, driving the inner term
        non-positive together with a large gain.
        """
        band = PEQBand("lowshelf", 105.0, 30.0, 0.7, slope=2.0)
        monkeypatch.setattr(peq, "min", lambda *a, **k: 2.0, raising=False)
        assert band.shelf_q == 0.707


class TestDefaultGraphicEqProfileName:
    def test_returns_31_band_for_large_budget(self):
        assert _default_graphic_eq_profile_name(31) == "geq_31_band"
        assert _default_graphic_eq_profile_name(50) == "geq_31_band"

    def test_returns_10_band_for_small_budget(self):
        assert _default_graphic_eq_profile_name(10) == "geq_10_band"
        assert _default_graphic_eq_profile_name(0) == "geq_10_band"


class TestGraphicEqProfileLookup:
    def test_unknown_profile_raises_value_error(self):
        with pytest.raises(ValueError, match="Unsupported GraphicEQ profile"):
            graphic_eq_profile("does_not_exist")


class TestBiquadResponseUnsupportedKind:
    def test_unsupported_band_kind_raises(self):
        band = PEQBand("bogus", 1000.0, 1.0, 1.0)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="Unsupported band type"):
            biquad_response_db(np.array([1000.0]), 48000, band)


class TestSolveBandGainsEmpty:
    def test_no_bands_returns_empty_list(self):
        assert solve_band_gains_lsq([1000.0], [1.0], 48000, [], []) == []


class TestSameSignFractionEmpty:
    def test_empty_values_returns_zero(self):
        assert _same_sign_fraction(np.array([]), 1.0) == 0.0


class TestEdgeShelfCandidate:
    def test_no_edge_samples_returns_none(self):
        """When no frequencies fall in the edge band, return None (line 316)."""
        # All frequencies above 140 Hz -> lowshelf edge_mask is all-False.
        freqs = np.geomspace(200.0, 20000.0, 100)
        target = np.zeros_like(freqs)
        assert _edge_shelf_candidate(freqs, target, kind="lowshelf", max_gain_db=12.0) is None

    def test_mixed_sign_edge_returns_none(self):
        """A large but sign-inconsistent edge mean is rejected (line 323)."""
        freqs = np.geomspace(20.0, 20000.0, 300)
        target = np.zeros_like(freqs)
        mask = freqs <= 140
        idx = np.where(mask)[0]
        # Strong positive overall, but ~45% of the edge is negative so the
        # same-sign fraction drops below 0.7.
        target[mask] = 5.0
        target[idx[: int(len(idx) * 0.45)]] = -2.0
        # Sanity: edge mean is large and clearly different from the compare band.
        assert abs(_band_mean(freqs, target, 20, 140)) >= 1.25
        result = _edge_shelf_candidate(freqs, target, kind="lowshelf", max_gain_db=12.0)
        assert result is None


class TestSelectPeakingCandidateGainBelowMin:
    def test_candidate_below_min_gain_is_skipped(self):
        """Candidates whose |gain| < min_gain_db are skipped (line 398).

        With an impossibly high min_gain_db every candidate is filtered out and
        the selector returns None.
        """
        freqs = np.geomspace(20.0, 20000.0, 300)
        target = np.where((freqs > 900) & (freqs < 1100), 3.0, 0.0)
        objective = FitObjective.from_target(freqs, target, 48000)
        residual = objective.residual_db([])
        result = _select_peaking_candidate(
            objective,
            residual,
            [],
            max_gain_db=8.0,
            max_q=4.5,
            min_peak_db=0.0,
            min_gain_db=100.0,
            allow_nearby_same_sign=True,
        )
        assert result is None


class TestRefineBandsNoImprovement:
    def test_refinement_rejected_keeps_original_bands(self, monkeypatch):
        """If Nelder-Mead does not beat the 3% threshold, original bands are kept (line 445)."""
        freqs = np.geomspace(20.0, 20000.0, 300)
        target = np.where((freqs > 900) & (freqs < 1100), 3.0, 0.0)
        objective = FitObjective.from_target(freqs, target, 48000)
        bands = [
            PEQBand("peaking", 500.0, 2.0, 1.0),
            PEQBand("peaking", 2000.0, -2.0, 1.0),
        ]

        class _Result:
            fun = 1e9  # far worse than initial cost
            x = np.array([1000.0, 1.0, 1.0, 2000.0, 1.0, 1.0])

        import scipy.optimize as so

        monkeypatch.setattr(so, "minimize", lambda *a, **k: _Result())
        out = _refine_bands_jointly(objective, bands, max_gain_db=8.0, max_q=4.5)
        assert out is bands


class TestFitPeqUnsupportedFamily:
    def test_unsupported_family_raises(self):
        """fit_peq raises for a family that is neither graphic_eq nor peq (line 469)."""
        budget = dataclasses.replace(FilterBudget(family="peq", max_filters=4), family="weird")
        freqs = np.geomspace(20.0, 20000.0, 100)
        with pytest.raises(ValueError, match="Unsupported filter family"):
            fit_peq(freqs, np.zeros_like(freqs), 48000, budget=budget)  # type: ignore[arg-type]


class TestFitPeqExactNBreak:
    def test_exact_n_breaks_when_no_candidate(self, monkeypatch):
        """exact_n loop breaks when even the fully relaxed selection yields no
        candidate (line 525). The fully relaxed selector cannot return None for a
        non-empty grid, so we mock it to None to drive the defensive break."""
        freqs = np.geomspace(20.0, 20000.0, 60)
        target = np.zeros_like(freqs)
        monkeypatch.setattr(peq, "_select_peaking_candidate", lambda *a, **k: None)
        budget = FilterBudget(family="peq", max_filters=3, fill_policy="exact_n")
        bands = fit_peq(freqs, target, 48000, budget=budget)
        assert bands == []
