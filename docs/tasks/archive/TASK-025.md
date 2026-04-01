# TASK-025 — Add end-to-end integration tests for synthetic measurement workflows

## Summary
Add integration tests that exercise the main CLI-facing measurement workflows against synthetic audio with known deviations.

## Context
The unit and component tests are now reasonably broad, but the next confidence gap is end-to-end behavior. We want to verify that the shared workflow can take controlled synthetic inputs, analyze them, fit toward a flat target, and produce the expected outputs.

## Scope
- Build synthetic measurement fixtures with known tonal deviations and channel differences.
- Add end-to-end tests for the main measurement-to-fit workflow.
- Validate that generated outputs exist and the fitted result improves error versus the uncorrected input.
- Keep the tests deterministic and fast enough for regular CI use.

## Out of scope
- Real PipeWire device tests.
- GUI automation.
- Performance benchmarking.

## Acceptance criteria
- At least one integration test exercises the main CLI/pipeline flow against synthetic input.
- The test verifies measurable improvement toward the target.
- The test validates the main generated artifacts.
- The test is deterministic and passes in CI.

## Suggested files/components
- `tests/test_integration_cli.py`
- `tests/test_pipeline.py`
- `headmatch/pipeline.py`
- `headmatch/cli.py`
