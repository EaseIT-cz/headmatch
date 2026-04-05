# TASK-087: PortAudio audio backend for macOS

## Summary
Implement `backend_portaudio.py` using the `sounddevice` library, fulfilling the `AudioBackend` protocol defined in `audio_backend.py`.

## Context
Phase 1 (backend extraction) is done. The `AudioBackend` protocol and `get_audio_backend()` factory are in place. This task implements the macOS-compatible backend.

## Scope
- `headmatch/backend_portaudio.py` implementing `AudioBackend`:
  - `discover_devices()` via `sounddevice.query_devices()`
  - `get_default_devices()` via `sounddevice.default.device`
  - `resolve_device_selection()` with saved target matching
  - `play_and_record()` via `sounddevice.playrec()` (simultaneous play+record)
  - `format_device_list()` for CLI display
  - `collect_doctor_checks()` — check sounddevice import, PortAudio availability, device count
- `sounddevice` added as optional dependency in `pyproject.toml` (extra: `[portaudio]`)
- Tests with mocked `sounddevice` — no real audio hardware needed

## Out of scope
- Real-device latency calibration (handled by existing alignment code in analysis.py)
- ASIO / exclusive mode on Windows
- GUI wording changes (separate task)

## Acceptance criteria
- `pip install headmatch[portaudio]` pulls in sounddevice
- On macOS: `get_audio_backend()` returns `PortAudioBackend`
- `headmatch list-targets` shows CoreAudio devices on macOS
- `headmatch doctor` reports PortAudio status on macOS
- `headmatch measure` plays and records via sounddevice
- All existing Linux/PipeWire tests still pass
- ≥10 new tests for the PortAudio backend (mocked)

## Suggested files
- `headmatch/backend_portaudio.py` (new)
- `pyproject.toml` (optional dep)
- `tests/test_backend_portaudio.py` (new)

## Priority
High — this is the core macOS enabler.
