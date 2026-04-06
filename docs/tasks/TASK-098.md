# TASK-098: Add release-gate job to verify sdist packaging

## Summary
Add a release-gate CI job that builds the sdist, installs it, and runs tests before any release.

## Context
The MANIFEST.in issue in 0.6.1rc1 went unnoticed because tests were only run against the repo checkout, not the built tarball. A release-gate job would have caught this.

## Scope
- Create new CI workflow (`.github/workflows/release-gate.yml`)
- Workflow steps:
  - Checkout code
  - Set up Python
  - Install `build` and `pytest`
  - Run `python -m build --sdist`
  - Install the built tarball into a fresh venv (or use `pip install --force-reinstall` in isolated venv)
  - Run `pytest` on the installed package

## Out-of-scope
- Publishing to PyPI (handled by existing `pypi-publish.yml`)
- Building binary releases (handled by `release-binary.yml`)

## Acceptance criteria
- After `v*` tag push or workflow dispatch, release-gate job:
  - Runs `python -m build --sdist`
  - Installs from sdist
  - Runs full test suite against installed version
  - Fails before release if any test fails

## Suggested files/components
- `.github/workflows/release-gate.yml`
