# TASK-115 - Async audio backend

## Summary
Replace `time.sleep()` synchronization in `play_and_record()` with asyncio-based process management.

## Context
The current PipeWire play_and_record implementation uses time.sleep() for synchronization between playback and recording subprocesses. An asyncio-based approach would be more robust and enable progress reporting without polling.

This is a lower-priority improvement that would benefit from careful design.

## Scope
- Research asyncio subprocess patterns for simultaneous play/record
- Design async interface for AudioBackend protocol
- Implement async version of PipeWire backend
- Add progress callback support
- Consider backward compatibility for sync callers

## Out of scope
- Changing audio pipeline logic
- Adding GUI progress updates (separate task)
- PortAudio backend (can follow later)

## Acceptance criteria
- Async play_and_record works reliably
- Progress reporting possible
- Existing tests pass
- No regression in audio quality/sync

## Suggested files/components
- `headmatch/backend_pipewire.py`
- `headmatch/audio_backend.py`
- New async test fixtures
