# TASK-112 - Add coverage CI gate

## Summary
Add a CI step that fails if coverage drops below a threshold (80%).

## Context
The codebase now has 80% coverage. A CI gate would prevent silent coverage erosion. The existing `pragma: no cover` markers should be reviewed and removed where tests exist.

## Scope
- Add coverage threshold check to CI
- Remove spurious `pragma: no cover` markers where tests exist
- Document intentional coverage exclusions
- Consider adding coverage badge to README

## Out of scope
- Writing new tests for uncovered code (separate tasks)
- Changing coverage configuration

## Acceptance criteria
- CI fails if coverage < 80%
- Spurious `pragma: no cover` markers removed
- Full test suite passes

## Suggested files/components
- `.github/workflows/coverage.yml`
- Any files with `pragma: no cover`
