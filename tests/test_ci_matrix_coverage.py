"""Pin the CI workflow split between the test matrix and the coverage gate.

`pytest.yml` runs the full Python 3.10-3.13 matrix; `coverage.yml` is a
dedicated single-version gate that fails the build when total coverage drops
below ``MIN_COVERAGE``. These tests keep that split — and the gate itself —
from silently drifting.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml


WORKFLOWS_DIR = Path(__file__).parent.parent / ".github" / "workflows"

# The workflow directory is absent when the tests run from an installed
# package rather than a checkout; there is nothing to pin in that case.
pytestmark = pytest.mark.skipif(
    not WORKFLOWS_DIR.is_dir(),
    reason="no .github/workflows directory (not running from a checkout)",
)

SUPPORTED_PYTHON_VERSIONS = ["3.10", "3.11", "3.12", "3.13"]
COVERAGE_GATE_PYTHON_VERSION = "3.13"

# The floor that TASK-112 established. The gate may be raised over time, but
# never lowered below this without a deliberate edit here.
MINIMUM_COVERAGE_FLOOR = 80


def _load_workflow(name: str) -> dict:
    path = WORKFLOWS_DIR / name
    assert path.exists(), f"{name} not found at {path}"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _triggers(workflow: dict) -> dict:
    """Return the ``on:`` block.

    YAML 1.1 resolves the bare key ``on`` to the boolean ``True``, so the
    parsed mapping keys it under ``True`` rather than ``"on"``.
    """
    return workflow.get("on", workflow.get(True)) or {}


@pytest.fixture
def pytest_workflow():
    return _load_workflow("pytest.yml")


@pytest.fixture
def coverage_workflow():
    return _load_workflow("coverage.yml")


def test_pytest_workflow_covers_the_supported_matrix(pytest_workflow):
    """pytest.yml runs every supported Python version."""
    matrix = pytest_workflow["jobs"]["pytest"]["strategy"]["matrix"]
    versions = [str(v) for v in matrix["python-version"]]

    missing = [v for v in SUPPORTED_PYTHON_VERSIONS if v not in versions]
    assert not missing, (
        f"pytest.yml matrix is missing Python {missing}; got {versions}"
    )


def test_coverage_workflow_is_a_single_version_gate(coverage_workflow):
    """coverage.yml is a dedicated gate, not a second matrix."""
    job = coverage_workflow["jobs"]["coverage"]

    assert "matrix" not in job.get("strategy", {}), (
        "coverage.yml should not fan out over a matrix; the matrix lanes "
        "belong to pytest.yml"
    )

    setup = [
        step for step in job["steps"] if "setup-python" in str(step.get("uses", ""))
    ]
    assert len(setup) == 1, "expected exactly one setup-python step in coverage.yml"
    assert str(setup[0]["with"]["python-version"]) == COVERAGE_GATE_PYTHON_VERSION


def test_coverage_workflow_enforces_the_floor(coverage_workflow):
    """The gate actually fails the build below MIN_COVERAGE."""
    job = coverage_workflow["jobs"]["coverage"]

    declared = int(job["env"]["MIN_COVERAGE"])
    assert declared >= MINIMUM_COVERAGE_FLOOR, (
        f"coverage floor regressed to {declared}%; TASK-112 set it at "
        f"{MINIMUM_COVERAGE_FLOOR}%"
    )

    run_steps = " ".join(step.get("run", "") for step in job["steps"])
    assert "--cov=headmatch" in run_steps, "coverage.yml must measure the package"
    assert "--cov-fail-under=${MIN_COVERAGE}" in run_steps, (
        "coverage.yml must fail under MIN_COVERAGE; without this flag the "
        "gate reports coverage but never blocks a regression"
    )


@pytest.mark.parametrize("name", ["pytest.yml", "coverage.yml"])
def test_workflows_run_on_the_same_triggers(name):
    """Both workflows fire on PRs and on pushes to main, so they run together."""
    triggers = _triggers(_load_workflow(name))

    assert "pull_request" in triggers, f"{name} should run on pull requests"
    assert "main" in (triggers.get("push") or {}).get("branches", []), (
        f"{name} should run on pushes to main"
    )
