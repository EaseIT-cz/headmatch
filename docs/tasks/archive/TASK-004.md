# TASK-004 — Harden device and recording validation

## Summary
Improve error handling for missing devices, bad sample rates, and malformed recordings.

## Context
The most fragile part of the product is the external measurement setup. Beginners need actionable failures, not stack traces.

## Scope
- Validate inputs earlier.
- Improve error messages for PipeWire capture/playback.
- Make sample-rate mismatch errors more specific.
- Detect obviously invalid recordings before fitting.

## Out of scope
- Device auto-discovery redesign.
- Major capture architecture rewrite.

## Acceptance criteria
- Common setup mistakes produce clear, actionable errors.
- The command explains what the user should fix.
- Tests cover at least the major failure cases.

## Suggested files/components
- `headmatch/measure.py`
- `headmatch/analysis.py`
- `headmatch/cli.py`
- `tests/`
