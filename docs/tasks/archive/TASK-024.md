# TASK-024 — Add clone examples and validate curve-source behavior

## Summary
Improve the target/cloning layer with better examples and broader validation across realistic curve inputs.

## Context
Clone workflows are useful, but users still need more examples and stronger validation that different curve sources behave consistently.

## Scope
- Add example clone targets and documentation for common headphone-pair usage.
- Validate clone generation across multiple curve-source shapes.
- Expand target-loading support only where new real-world formats justify it.

## Out of scope
- Building a target-curve database.
- New file formats without a clear need.
- UI redesign.

## Acceptance criteria
- Example clone assets/docs are discoverable.
- Clone behavior is validated against multiple source shapes.
- Any new target-loading support is covered by tests.

## Suggested files/components
- `headmatch/targets.py`
- `README.md`
- `docs/examples/`
- `tests/`
