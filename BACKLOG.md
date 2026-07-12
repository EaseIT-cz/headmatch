<!-- vornik backlog v1 — markers: [ ] pending | [?] proposed | [x] done | [!] failed -->

# HeadMatch Backlog (autonomy-processed)

The vornik daemon (project `headmatch`, `mode: backlog`) consumes the **first
`- [ ]` item** each tick, runs it through the `backlog-item` workflow
(analyze → implement → test → review → draft PR), then stamps the line
`- [x] … (task: <id>)` on success or `- [!]` on failure. `- [?]` items are
**proposed** and stay inert until an operator promotes them to `- [ ]` — the
per-item human gate. Deposited findings also land as `- [?]`.

Keep each item a **single, self-contained line**: the whole line becomes the
task prompt, and the agent works only that item ("smallest correct fix with
tests"). The narrative capabilities + release history live in `docs/backlog.md`.

## Ready

- [x] TASK-113: Document the confidence-scoring derivation — add docstrings and inline rationale for the magic numbers in `pipeline_confidence.py`, plus a short note under `docs/`. No behaviour change; add a test that pins the current scores so the documentation cannot silently drift. (task: task_20260712004844_3bf3db60b5a334dd)
- [x] TASK-112: Add a coverage CI gate — fail CI when total coverage drops below the current 80% level, wired into the existing GitHub Actions matrix without breaking the Python 3.10–3.13 lanes. (task: task_20260712021844_d6e14940dba6130b)
- [x] TASK-114: Harden `fetch_curve_from_url` against SSRF — validate the URL scheme and host against a domain allowlist (the known measurement databases) before fetching, and reject private / loopback / link-local targets. Add tests for allowed and rejected URLs. (task: task_20260712034844_5c385e9f59a31f3c)
- [x] TASK-110: Standardize the error hierarchy — define a `HeadMatchError` base class with `MeasurementError`, `ConfigError`, and `NetworkError` subclasses and migrate the existing raise sites to them; keep messages intact and add tests asserting the new types are raised. (task: task_20260712051844_0ef3ce20f1615424)
- [x] TASK-109: Decompose `gui/shell.py` — extract `GuiState` into its own module and break out the Tkinter variable initialization, leaving `gui/shell.py` a thin composition. No UI behaviour change; keep the existing GUI tests green. (task: task_20260712064844_7720364a5e21b289)
- [!] TASK-106: Split `gui_views.py` into real per-view modules (one module per view) with a package `__init__` re-export so imports stay stable. No behaviour change; tests stay green. (task: task_20260712081844_2d41a0f40a8c73c4, failed)
- [x] TASK-107: Extract the GUI workflow controllers out of `HeadMatchGuiApp` into dedicated controller classes, leaving `HeadMatchGuiApp` as wiring. No behaviour change; tests stay green. (task: task_20260712094844_55b5735c44ba96df)
- [ ] TASK-108: Centralize GUI file-picking and background-task helpers into a shared module and route the existing call sites through it. No behaviour change; tests stay green.

## Proposed — promote to `- [ ]` when ready (some may already be shipped; vet first)

- [?] TASK-115: Async audio backend — replace `time.sleep()` synchronization with asyncio-based process management across the audio backends. Large refactor; wants a design pass before it is a single task.
- [?] Dense GraphicEQ clipping — validate the added 1.5 dB headroom holds in real-world use (may still clip). Needs real measurement data, not a pure code change.
- [?] macOS real-hardware end-to-end testing — CI passes but the PortAudio path needs manual validation on real hardware (not autonomously doable).
- [?] Mic-calibration workflow (research) — derive a mic response curve via trusted-data comparison; open questions on reliable databases, ear-canal resonance variation, and per-user tractability.
- [?] Packaging — macOS `.app` bundle, Windows `.exe` (PyInstaller), and Linux AppImage wrappers (currently shipped as raw binaries).
- [?] Target-editor polish — keyboard shortcuts plus undo/redo.
- [?] Cache fixed-profile basis responses for repeated GraphicEQ runs.
- [?] Additional export formats beyond CamillaDSP and Equalizer APO.
- [?] CamillaDSP live-update via its WebSocket API.
- [?] Closed-loop EQ refinement (measure → apply → re-measure).
