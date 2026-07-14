"""Tests for contract dataclasses and type aliases."""

from typing import get_args

import pytest

from headmatch.contracts import FrontendConfig, FrontendRunSummary, WorkflowName


# --- WorkflowName tests (Literal type) ---

def test_workflow_name_includes_room():
    """WorkflowName should include 'room' as a valid workflow step."""
    args = set(get_args(WorkflowName))
    assert "room" in args


def test_workflow_name_has_expected_workflows():
    """WorkflowName should include expected workflow steps."""
    args = set(get_args(WorkflowName))
    expected = {
        "start",
        "measure",
        "prepare-offline",
        "analyze",
        "fit",
        "iterate",
        "clone-target",
        "hearing-test",
        "hearing-fit",
        "room",
    }
    assert args == expected


# --- FrontendConfig tests ---

def test_frontend_config_has_preferred_mic_cal_csv():
    """FrontendConfig should have preferred_mic_cal_csv field."""
    config = FrontendConfig()
    assert hasattr(config, 'preferred_mic_cal_csv')
    # Default should be None
    assert config.preferred_mic_cal_csv is None


def test_frontend_config_preferred_mic_cal_csv_can_be_set():
    """preferred_mic_cal_csv can be set to a path string."""
    config = FrontendConfig(preferred_mic_cal_csv="/path/to/mic_cal.csv")
    assert config.preferred_mic_cal_csv == "/path/to/mic_cal.csv"


def test_frontend_config_preferred_mic_cal_csv_to_dict():
    """preferred_mic_cal_csv should be included in to_dict output."""
    config = FrontendConfig(preferred_mic_cal_csv="/path/to/mic_cal.csv")
    d = config.to_dict()
    assert d["preferred_mic_cal_csv"] == "/path/to/mic_cal.csv"


# --- FrontendRunSummary room-specific field tests ---

def test_frontend_run_summary_has_cutoff_hz():
    """FrontendRunSummary should have cutoff_hz field."""
    from headmatch.contracts import ConfidenceSummary, RunErrorSummary, RunFilterCounts
    from headmatch.peq import FilterBudget

    summary = FrontendRunSummary(
        schema_version=1,
        kind="fit",
        out_dir="/tmp/test",
        sample_rate=48000,
        frequency_points=100,
        target="flat",
        filters=RunFilterCounts(left=5, right=5),
        predicted_error_db=RunErrorSummary(
            left_rms=1.0, right_rms=1.0, left_max=2.0, right_max=2.0
        ),
        generated_by={"version": "1.0"},
        confidence=ConfidenceSummary(
            score=75,
            label="high",
            headline="Good fit",
            interpretation="Test",
            reasons=(),
            warnings=(),
            metrics={},
        ),
        plots={},
        results_guide="/tmp/test/README.txt",
        cutoff_hz=300.0,
    )
    assert summary.cutoff_hz == 300.0


def test_frontend_run_summary_accepts_room_kind():
    """Room fits should be identifiable without overloading generic fit kind."""
    from headmatch.contracts import ConfidenceSummary, RunErrorSummary, RunFilterCounts

    summary = FrontendRunSummary(
        schema_version=1,
        kind="room",
        out_dir="/tmp/test",
        sample_rate=48000,
        frequency_points=100,
        target="room_modal_flat",
        filters=RunFilterCounts(left=5, right=5),
        predicted_error_db=RunErrorSummary(
            left_rms=1.0, right_rms=1.0, left_max=2.0, right_max=2.0
        ),
        generated_by={"version": "1.0"},
        confidence=ConfidenceSummary(
            score=75,
            label="high",
            headline="Good room fit",
            interpretation="Test",
            reasons=(),
            warnings=(),
            metrics={},
        ),
        plots={},
        results_guide="/tmp/test/README.txt",
        cutoff_hz=300.0,
    )

    assert summary.to_dict()["kind"] == "room"


def test_frontend_run_summary_has_mic_cal_applied():
    """FrontendRunSummary should have mic_cal_applied field."""
    from headmatch.contracts import ConfidenceSummary, RunErrorSummary, RunFilterCounts

    summary = FrontendRunSummary(
        schema_version=1,
        kind="fit",
        out_dir="/tmp/test",
        sample_rate=48000,
        frequency_points=100,
        target="flat",
        filters=RunFilterCounts(left=5, right=5),
        predicted_error_db=RunErrorSummary(
            left_rms=1.0, right_rms=1.0, left_max=2.0, right_max=2.0
        ),
        generated_by={"version": "1.0"},
        confidence=ConfidenceSummary(
            score=75,
            label="high",
            headline="Good fit",
            interpretation="Test",
            reasons=(),
            warnings=(),
            metrics={},
        ),
        plots={},
        results_guide="/tmp/test/README.txt",
        mic_cal_applied=True,
    )
    assert summary.mic_cal_applied is True


def test_frontend_run_summary_has_single_point():
    """FrontendRunSummary should have single_point field."""
    from headmatch.contracts import ConfidenceSummary, RunErrorSummary, RunFilterCounts

    summary = FrontendRunSummary(
        schema_version=1,
        kind="fit",
        out_dir="/tmp/test",
        sample_rate=48000,
        frequency_points=100,
        target="flat",
        filters=RunFilterCounts(left=5, right=5),
        predicted_error_db=RunErrorSummary(
            left_rms=1.0, right_rms=1.0, left_max=2.0, right_max=2.0
        ),
        generated_by={"version": "1.0"},
        confidence=ConfidenceSummary(
            score=75,
            label="high",
            headline="Good fit",
            interpretation="Test",
            reasons=(),
            warnings=(),
            metrics={},
        ),
        plots={},
        results_guide="/tmp/test/README.txt",
        single_point=False,
    )
    assert summary.single_point is False





def test_frontend_run_summary_room_fields_in_to_dict():
    """Room-specific fields should appear in to_dict output."""
    from headmatch.contracts import ConfidenceSummary, RunErrorSummary, RunFilterCounts

    summary = FrontendRunSummary(
        schema_version=1,
        kind="fit",
        out_dir="/tmp/test",
        sample_rate=48000,
        frequency_points=100,
        target="flat",
        filters=RunFilterCounts(left=5, right=5),
        predicted_error_db=RunErrorSummary(
            left_rms=1.0, right_rms=1.0, left_max=2.0, right_max=2.0
        ),
        generated_by={"version": "1.0"},
        confidence=ConfidenceSummary(
            score=75,
            label="high",
            headline="Good fit",
            interpretation="Test",
            reasons=(),
            warnings=(),
            metrics={},
        ),
        plots={},
        results_guide="/tmp/test/README.txt",
        cutoff_hz=300.0,
        mic_cal_applied=True,
        single_point=True,
    )
    d = summary.to_dict()
    assert d["cutoff_hz"] == 300.0
    assert d["mic_cal_applied"] is True
    assert d["single_point"] is True


def test_frontend_run_summary_from_dict_includes_room_fields():
    """from_dict should parse room-specific fields correctly."""
    from headmatch.contracts import RUN_SUMMARY_SCHEMA_VERSION

    payload = {
        "schema_version": RUN_SUMMARY_SCHEMA_VERSION,
        "kind": "fit",
        "out_dir": "/tmp/test",
        "sample_rate": 48000,
        "frequency_points": 100,
        "target": "flat",
        "filters": {"left": 5, "right": 5},
        "predicted_error_db": {
            "left_rms": 1.0,
            "right_rms": 1.0,
            "left_max": 2.0,
            "right_max": 2.0,
        },
        "generated_by": {"version": "1.0"},
        "confidence": {
            "score": 75,
            "label": "high",
            "headline": "Good fit",
            "interpretation": "Test",
            "reasons": [],
            "warnings": [],
            "metrics": {},
        },
        "plots": {},
        "results_guide": "/tmp/test/README.txt",
        "cutoff_hz": 300.0,
        "mic_cal_applied": True,
        "single_point": True,
    }

    summary = FrontendRunSummary.from_dict(payload)
    assert summary.cutoff_hz == 300.0
    assert summary.mic_cal_applied is True
    assert summary.single_point is True
