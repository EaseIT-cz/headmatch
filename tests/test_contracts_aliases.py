"""Tests for RunFilterCounts and RunErrorSummary dataclass contracts."""
from headmatch.contracts import RunFilterCounts, RunErrorSummary


def test_run_filter_counts_to_dict():
    rfc = RunFilterCounts(left=5, right=3)
    d = rfc.to_dict()
    assert d == {"left": 5, "right": 3}


def test_run_filter_counts_has_no_output_target():
    """Ensure copy-pasted alias properties are gone."""
    rfc = RunFilterCounts(left=5, right=3)
    assert not hasattr(type(rfc), "output_target")
    assert not hasattr(type(rfc), "input_target")


def test_run_error_summary_to_dict():
    res = RunErrorSummary(left_rms=1.0, right_rms=2.0, left_max=3.0, right_max=4.0)
    d = res.to_dict()
    assert d == {"left_rms": 1.0, "right_rms": 2.0, "left_max": 3.0, "right_max": 4.0}


def test_run_error_summary_has_no_output_target():
    """Ensure copy-pasted alias properties are gone."""
    res = RunErrorSummary(left_rms=1.0, right_rms=2.0, left_max=3.0, right_max=4.0)
    assert not hasattr(type(res), "output_target")
    assert not hasattr(type(res), "input_target")
