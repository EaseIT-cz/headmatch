# Current Task: Unit Test Coverage for 5 Functions

**Feature:** Add unit tests for 5 functions to improve coverage
**Issue:** https://github.com/EaseIT-cz/headmatch/issues/17
**Status:** in-progress

## Background

Current coverage is 89% overall, but several modules need improvement:
- `audio_backend.py` (78%)
- `backend_pipewire.py` (72%)
- `gui/shell.py` (72%)
- `gui/controllers.py` (79%)
- `gui/views/_legacy.py` (31%)

Testing 5 uncovered functions from these modules will improve coverage.

---

## Subtasks

### [!] Subtask 1: Test `_classify_media_class` in `backend_pipewire.py` — blocked: agent_error: podman wait timed out after 7m30s
Files: `tests/test_backend_pipewire.py`
Implementation note: Add unit tests for the helper function that classifies media classes.

test_cases:
  - id: case_1
    description: Returns 'playback' for Audio/Sink media class
    inputs: "Audio/Sink"
    expected: "playback"
    kind: unit
  - id: case_2
    description: Returns 'capture' for Audio/Source media class
    inputs: "Audio/Source"
    expected: "capture"
    kind: unit
  - id: case_3
    description: Returns 'capture' for Audio/Source/Virtual media class
    inputs: "Audio/Source/Virtual"
    expected: "capture"
    kind: unit
  - id: case_4
    description: Returns None for non-audio media class
    inputs: "Video/Source"
    expected: null
    kind: unit
  - id: case_5
    description: Returns None for empty string
    inputs: ""
    expected: null
    kind: unit

### Subtask 2: Test `_parse_pw_dump` in `backend_pipewire.py`
Files: `tests/test_backend_pipewire.py`
Implementation note: Add unit tests for parsing PipeWire JSON payload.

test_cases:
  - id: case_1
    description: Parses valid payload with playback device
    inputs: [{"info": {"props": {"media.class": "Audio/Sink", "node.name": "alsa_output"}}}]
    expected: List containing one AudioDevice with kind="playback", device_id="alsa_output"
    kind: unit
  - id: case_2
    description: Parses valid payload with capture device
    inputs: [{"info": {"props": {"media.class": "Audio/Source", "node.name": "alsa_input"}}}]
    expected: List containing one AudioDevice with kind="capture", device_id="alsa_input"
    kind: unit
  - id: case_3
    description: Skips items missing node.name
    inputs: [{"info": {"props": {"media.class": "Audio/Sink"}}}]
    expected: Empty list
    kind: unit
  - id: case_4
    description: Returns empty list for empty payload
    inputs: []
    expected: Empty list
    kind: unit

### Subtask 3: Test `_parse_wpctl_default_ids` in `backend_pipewire.py`
Files: `tests/test_backend_pipewire.py`
Implementation note: Add unit tests for parsing wpctl status output.

test_cases:
  - id: case_1
    description: Parses default playback device from wpctl status
    inputs: |
      Sinks:
        * 45. some_sink_name
    expected: {"playback": 45}
    kind: unit
  - id: case_2
    description: Parses default capture device from wpctl status
    inputs: |
      Sources:
        * 67. some_source_name
    expected: {"capture": 67}
    kind: unit
  - id: case_3
    description: Returns empty dict when no default marked
    inputs: |
      Sinks:
        45. some_sink_name
    expected: {}
    kind: unit
  - id: case_4
    description: Parses both playback and capture defaults
    inputs: |
      Sinks:
        * 45. sink_name
      Sources:
        * 67. source_name
    expected: {"playback": 45, "capture": 67}
    kind: unit

### Subtask 4: Test `_require_target` in `backend_pipewire.py`
Files: `tests/test_backend_pipewire.py`
Implementation note: Add unit tests for the target validation helper.

test_cases:
  - id: case_1
    description: Returns stripped string for valid value
    inputs: ("  valid_target  ", "label")
    expected: "valid_target"
    kind: unit
  - id: case_2
    description: Returns None when input is None
    inputs: (null, "label")
    expected: null
    kind: unit
  - id: case_3
    description: Raises ValueError for empty string after stripping
    inputs: ("   ", "output_target")
    expected: Raises ValueError with message "output_target cannot be empty"
    kind: unit
  - id: case_4
    description: Raises ValueError for whitespace-only string
    inputs: ("\t\n", "input_target")
    expected: Raises ValueError with message "input_target cannot be empty"
    kind: unit

### Subtask 5: Test `get_audio_backend` in `audio_backend.py`
Files: `tests/test_audio_backend.py`
Implementation note: Add unit tests for the backend auto-detection function.

test_cases:
  - id: case_1
    description: Returns PipeWireBackend on Linux
    inputs: "linux"
    expected: Instance of PipeWireBackend
    kind: unit
  - id: case_2
    description: Returns PortAudioBackend on macOS
    inputs: "darwin"
    expected: Instance of PortAudioBackend
    kind: unit
  - id: case_3
    description: Returns PortAudioBackend on Windows
    inputs: "win32"
    expected: Instance of PortAudioBackend
    kind: unit
  - id: case_4
    description: Raises RuntimeError on unsupported platform
    inputs: "unsupported_platform"
    expected: Raises RuntimeError with message containing "No audio backend available"
    kind: unit

---

## Acceptance Criteria

- [ ] At least 5 new functions have unit test coverage
- [ ] All new tests pass
- [ ] Overall coverage increases from 89%