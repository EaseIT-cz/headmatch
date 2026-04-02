# TASK-052 — Publish the package to PyPI from GitHub Releases using build artifacts

## Summary
Add GitHub Actions release automation so a published GitHub Release triggers PyPI publication using artifacts produced by `package-build.yml`.

## Context
The repo now builds package artifacts in CI, but it does not yet publish them. The desired model is:
- `package-build.yml` remains the artifact producer
- a release-triggered workflow publishes the built artifacts to PyPI
- the publish flow should use the build artifacts rather than rebuilding independently in the publish job

## Scope
- Add a release-triggered GitHub Actions workflow for PyPI publication.
- Use artifacts produced by `package-build.yml`.
- Keep the workflow simple and compatible with modern PyPI publishing practices.
- Update `package-build.yml` only if needed to make release artifacts discoverable/reusable.
- Update docs only if strictly necessary.

## Out of scope
- TestPyPI publishing.
- Full release-note automation.
- GUI/app changes.
- Non-PyPI distribution channels.

## Acceptance criteria
- A published GitHub Release can trigger PyPI publication.
- The publish workflow consumes artifacts built by `package-build.yml` instead of rebuilding.
- The workflow is compatible with secure GitHub Actions-based publishing.
- Existing package build automation remains intact.

## Suggested files/components
- `.github/workflows/package-build.yml`
- `.github/workflows/` (new release publish workflow)
- docs only if needed
