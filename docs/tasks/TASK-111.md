# TASK-111 - Add type checking CI

## Summary
Add mypy or pyright to CI pipeline to catch type errors at development time rather than runtime.

## Context
The codebase uses type hints extensively but has no automated type checking. The code review found bugs like the `RunFilterCounts` property error that would have been caught by a type checker.

## Scope
- Add mypy or pyright configuration (pyproject.toml or separate config)
- Add CI step that runs type checking
- Fix any existing type errors
- Add `TYPE_CHECKING` imports where needed to avoid circular imports during checking

## Out of scope
- Full strict mode (incremental adoption)
- Adding type hints to untyped code
- Changing existing type annotations

## Acceptance criteria
- Type checker runs in CI
- CI passes with no errors
- Configuration allows incremental adoption

## Suggested files/components
- `pyproject.toml` (mypy or pyright section)
- `.github/workflows/test.yml` (add type-check step)
