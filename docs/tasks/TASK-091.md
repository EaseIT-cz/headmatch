# TASK-091: PyInstaller spec and build script for Linux x64

## Summary
Create a PyInstaller spec file and build script that produces a single-file Linux x64 executable for the GUI.

## Context
Users shouldn't need Python installed. PyInstaller bundles Python + deps into one file. Linux first; macOS/Windows later.

## Scope
- `headmatch.spec` — PyInstaller spec file for the GUI entrypoint
  - Bundles: numpy, scipy, soundfile, pyyaml, tkinter, headmatch package
  - Excludes: sounddevice (Linux uses PipeWire, not PortAudio)
  - Includes: `docs/examples/targets/` data files
  - Single-file mode (`--onefile`)
  - Named output: `headmatch-gui`
- `scripts/build.py` — build helper that:
  - Installs PyInstaller if needed
  - Runs the spec
  - Reports output size
  - Validates the binary runs `--version`
- Test: binary runs `headmatch-gui --help` without Python installed (CI will verify)

## Out of scope
- macOS .app bundle (later task)
- AppImage wrapper (later task — single file is enough for now)
- CLI-only binary (GUI is the primary product surface)
- Code signing

## Acceptance criteria
- `python scripts/build.py` produces `dist/headmatch-gui` on Linux x64
- Binary launches the GUI without Python on PATH
- Binary size < 200MB (ideally < 150MB)
- Build completes in < 5 minutes on GitHub Actions runner

## Suggested files
- `headmatch.spec` (new)
- `scripts/build.py` (new)

## Priority
High — prerequisite for CI automation.
