# TASK-092: GitHub Actions workflow for Linux binary release

## Summary
Automate Linux x64 binary builds on GitHub Actions, attached to GitHub Releases.

## Context
TASK-091 produces the build script. This task automates it so every tagged release gets a downloadable binary.

## Scope
- `.github/workflows/release-binary.yml`:
  - Trigger: push of `v*` tags
  - Runner: `ubuntu-latest`
  - Steps: checkout, setup Python 3.11, install deps + PyInstaller, run build script, upload artifact
  - Attach `headmatch-gui-linux-x64` to the GitHub Release
- Smoke test step: run the binary with `--help` to verify it works before upload
- Use `softprops/action-gh-release` or similar for release attachment

## Out of scope
- macOS/Windows matrix builds (later)
- PyPI publish automation (separate concern)
- Nightly builds

## Acceptance criteria
- Pushing `v0.6.1` tag triggers the workflow
- Workflow produces `headmatch-gui-linux-x64` attached to the GitHub Release
- Binary passes `--help` smoke test in CI

## Suggested files
- `.github/workflows/release-binary.yml` (new)

## Priority
High — depends on TASK-091.
