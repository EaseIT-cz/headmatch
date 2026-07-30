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
- [?] **[refactor]** Update test_gui.py to use WorkflowControllers for basic_search_target and choose_basic_search_match — The tests test_basic_search_with_multiple_matches_requires_choice and test_basic_search_single_match_downloads_and_selects_csv directly call HeadMatchGuiApp methods with a SimpleNamespace mock. After moving these methods to WorkflowControllers and adding delegation in shell.py, these tests now need to use WorkflowControllers instead of calling classmethods on HeadMatchGuiApp. (evidence: tests/test_gui.py:293-306 for multiple matches, tests/test_gui.py:323-344 for single match. These tests use SimpleNamespace without _controllers attribute.; via task_20260712095457_5b6438f138dd1e3c, 2026-07-12)
