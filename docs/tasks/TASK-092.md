# TASK-092: GitHub Actions workflow for Linux binary release

## Summary
Create a GitHub Actions workflow that builds and publishes Linux x64 binaries on tag push or manual dispatch.

## Context
We need a CI job that: (1) builds the PyInstaller binary using a full Python with shared lib, (2) tests the binary, (3) creates a GitHub release, (4) uploads the binary as an asset.

**Status: Blocked — depends on TASK-091 (binary build must work first).**

## Blockers

This task cannot proceed until `scripts/build.py --clean --binary` succeeds locally (TASK-091). The GitHub Actions workflow assumes a working build script.

## Human requirements (after TASK-091 is resolved)

### Step 1: Add workflow file

Create `.github/workflows/release-binary.yml` with a job that:

1. Checks out code
2. Installs system dependencies (including `python3-tk` via apt)
3. Installs Python dependencies (`pyinstaller`, `numpy`, `scipy`)
4. Runs `bash scripts/build.py --clean --binary`
5. Tests the binary (CLI and GUI)
6. Creates a GitHub release on `v*` tag
7. Uploads the binary as an asset

### Step 2: Test the workflow

Push a test tag (e.g., `v0.6.1-test`) and verify:
- Build succeeds
- Binary passes CLI/GUI test
- Release created with asset

## Scope

- ✅ Create `.github/workflows/release-binary.yml`
- ✅ Build PyInstaller binary on `ubuntu-latest`
- ✅ Test binary (CLI + GUI)
- ✅ Create GitHub release on tag push
- ✅ Upload Linux binary as release asset

## Out-of-scope

- Publishing to PyPI — handled by existing `pypi-publish.yml`
- macOS/Windows binaries — separate workflows

## Acceptance criteria

1. On push of `v*` tag, workflow runs
2. Binary builds successfully (no PyInstaller errors)
3. Binary passes CLI/GUI test
4. Release created with `headmatch-v*-*` asset
5. Downloaded binary runs on clean Ubuntu 22.04/24.04 VM

## Suggested files/components

- `.github/workflows/release-binary.yml`
- `headmatch.spec`
- `scripts/build.py`
