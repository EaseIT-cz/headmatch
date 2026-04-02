# TASK-048 — Automate package builds in GitHub Actions

## Summary
Add a GitHub Actions workflow that automatically builds HeadMatch package artifacts so the build path is exercised in CI instead of relying on manual local runs.

## Context
The repo already has separate unit/functional and integration pytest workflows, but it does not yet automate package builds. The user wants the process to be fully automated and the build to happen via GitHub Actions.

## Scope
- Add a GitHub Actions workflow that builds the Python package artifacts.
- Keep the workflow simple and maintainable.
- Reuse the existing Python packaging setup from `pyproject.toml`.
- Prefer build verification/artifact upload over release publishing automation at this stage.
- Update docs only if strictly necessary.

## Out of scope
- Automated release publishing to GitHub Releases or PyPI.
- Cross-platform packaging redesign.
- GUI changes.
- Backend/application behavior changes.

## Acceptance criteria
- GitHub Actions automatically builds package artifacts on PRs and pushes to main.
- The workflow fails if the build process breaks.
- Built artifacts are available as workflow artifacts.
- Existing test workflows remain intact.

## Suggested files/components
- `.github/workflows/`
- `pyproject.toml` only if a very small packaging tweak is required
