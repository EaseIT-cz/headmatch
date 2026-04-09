# HeadMatch 0.7.1 Release Notes

Released: 2026-04-10

## Overview

Post-code-review maintenance release with bug fixes, new CLI tools, and CI improvements.

## Bug Fixes

- **BUG-001**: Removed invalid `output_target`/`input_target` properties from `RunFilterCounts` and `RunErrorSummary` (copy-paste error from `FrontendConfig`)
- **BUG-002**: Deduplicated set literals in CLI command routing
- **BUG-003**: Empty headphone search now returns `[]` instead of entire database
- **BUG-004**: Fixed file handle leak in PipeWire `play_and_record()`
- **BUG-005**: Added frequency-range validation for downloaded FR curves
- **BUG-006**: Removed spurious `pragma: no cover` from error handler with test coverage

## New Features

### Batch Processing
- **batch-fit**: Process multiple recordings from a JSON manifest
  ```bash
  headmatch batch-fit --manifest batch.json
  headmatch batch-template --out batch.json --entries 5
  ```

### History & Comparison
- **history**: Review past measurement runs
  ```bash
  headmatch history --root out/ --limit 10
  ```
- **compare-runs**: Compare two recent runs side-by-side
  ```bash
  headmatch compare-runs --root out/
  ```
- **compare-ab**: A/B comparison tool with preset export
  ```bash
  headmatch compare-ab --run-a session_01/fit --run-b session_02/fit --out-dir comparison/
  ```

## UI/UX Improvements

- Basic-mode target guidance with dynamic help text
- Missing-device guidance in online wizard (troubleshooting steps)
- Confidence icons and clearer headers in history output

## Code Quality

- Added mypy type checking CI workflow
- Fixed 169 typing errors across 15 files
- `mypy` now passes cleanly on 48 source files

## Test Coverage

- **618 tests passing** (up from 591)
- Coverage: **80%** total (up from ~75%)
- All patches bisectable at every commit

## Upgrade Notes

No breaking changes. Upgrade with:
```bash
pip install --upgrade headmatch
```