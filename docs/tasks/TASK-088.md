# TASK-088: Platform-aware config and cache paths

## Summary
Use platform-appropriate directories for config and cache on macOS and Windows instead of hardcoded XDG/Linux paths.

## Context
Currently `settings.py` uses `~/.config/headmatch` and `headphone_db.py` uses `~/.cache/headmatch`. These are Linux conventions. macOS expects `~/Library/Application Support/` and `~/Library/Caches/`. Windows expects `%APPDATA%`.

## Scope
- Create `headmatch/paths.py` with `config_dir()` and `cache_dir()` helpers
  - Linux: `XDG_CONFIG_HOME` / `~/.config/headmatch`, `XDG_CACHE_HOME` / `~/.cache/headmatch`
  - macOS: `~/Library/Application Support/headmatch`, `~/Library/Caches/headmatch`
  - Windows: `%APPDATA%/headmatch`, `%LOCALAPPDATA%/headmatch/cache`
- Update `settings.py` and `headphone_db.py` to use the new helpers
- Existing Linux configs must keep working (no migration needed)

## Out of scope
- Config file format changes
- Migration tool for moving configs between platforms

## Acceptance criteria
- On macOS: config lands in `~/Library/Application Support/headmatch/`
- On Linux: behaviour unchanged (XDG paths)
- Tests verify correct paths per platform (mocked `sys.platform`)
- ≥6 new tests

## Suggested files
- `headmatch/paths.py` (new)
- `headmatch/settings.py` (update import)
- `headmatch/headphone_db.py` (update import)
- `tests/test_paths.py` (new)

## Priority
Medium — nice-to-have for correct macOS experience, not a blocker.
