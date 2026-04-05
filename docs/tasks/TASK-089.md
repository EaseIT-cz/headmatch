# TASK-089: Platform-aware GUI and CLI text

## Summary
Replace hardcoded "PipeWire" references in GUI labels, CLI help text, and doctor output with platform-aware alternatives.

## Context
GUI labels say "PipeWire playback and capture", CLI help mentions "PipeWire node.name", doctor checks reference pw-dump. On macOS these are confusing. The text should adapt to the active backend.

## Scope
- GUI labels: "Use this when audio playback and capture are available" (not "PipeWire")
- CLI help: "--output-target" description should say "audio device" not "PipeWire node"
- Doctor report: backend name in check labels ("PipeWire" on Linux, "CoreAudio" on macOS)
- `headmatch list-targets` header adapts to backend
- Config field names `pipewire_output_target` / `pipewire_input_target` → `output_target` / `input_target` with backward-compat aliases

## Out of scope
- Functional changes to measurement flow
- New backends

## Acceptance criteria
- No "PipeWire" text visible when running on macOS
- Linux behaviour and wording unchanged
- Config files with old field names still load correctly
- ≥4 tests for config field aliasing

## Suggested files
- `headmatch/gui_views.py` (label text)
- `headmatch/cli.py` (help strings)
- `headmatch/contracts.py` (field aliases)
- `headmatch/settings.py` (config loading compat)

## Priority
Low — cosmetic, can ship after functional macOS support works.
