"""Part A engine guards (0.8.3): honest convergence + flooring detection.

A threshold is only trustworthy when the Hughson-Westlake staircase truly
converged (>=3 ascending runs, 2-of-last-3). Cap-terminated or floored results
must NOT be reported as determined, and hearing the test floor must terminate
early and flag "volume too high".
"""
from __future__ import annotations

from headmatch.hearing_test import (
    FrequencyThreshold,
    MAX_PRESENTATIONS,
    MIN_LEVEL_DBFS,
    ThresholdEngine,
)


def _drive(engine, responder, limit=500):
    n = 0
    while not engine.done and n < limit:
        engine.record_response(responder(engine.current_level_dbfs))
        n += 1
    return n


def test_converged_true_on_real_convergence():
    eng = ThresholdEngine(1000)
    _drive(eng, lambda level: level >= -45.0)
    assert eng.done
    assert eng.converged is True
    assert eng.floored is False
    assert eng.threshold == -45.0


def test_hearing_everything_is_floored_not_converged():
    eng = ThresholdEngine(1000)
    _drive(eng, lambda _level: True)
    assert eng.done
    assert eng.converged is False
    assert eng.floored is True
    # Heard even the quietest tone -> threshold cannot be bracketed.
    assert eng.threshold is None


def test_flooring_terminates_early():
    eng = ThresholdEngine(1000)
    n = _drive(eng, lambda _level: True)
    # Descends to the floor in ~5 steps, then bails once the floor is heard a
    # couple of times — far short of the safety cap.
    assert n < 12


def test_missing_everything_is_undetermined_not_converged():
    eng = ThresholdEngine(1000)
    _drive(eng, lambda _level: False)
    assert eng.done
    assert eng.converged is False
    assert eng.floored is False
    assert eng.threshold is None


def test_safety_cap_allows_real_convergence():
    # The cap must be high enough that a legitimate staircase (~11 presentations)
    # converges instead of being cut off.
    assert MAX_PRESENTATIONS >= 20
    eng = ThresholdEngine(1000)
    n = _drive(eng, lambda level: level >= -45.0)
    assert eng.converged is True and n < MAX_PRESENTATIONS


def test_frequency_threshold_has_floored_field_default_false():
    t = FrequencyThreshold(freq_hz=1000, level_dbfs=-45.0, ascending_runs=3, determined=True)
    assert t.floored is False
