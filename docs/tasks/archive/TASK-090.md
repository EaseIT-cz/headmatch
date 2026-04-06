# TASK-090: macOS integration testing and release

## Summary
End-to-end testing of HeadMatch on macOS with real audio hardware, followed by a release.

## Context
After TASK-087 (PortAudio backend) and TASK-088 (platform paths), the codebase should be functionally ready for macOS. This task covers manual validation and release preparation.

## Scope
- Test `headmatch doctor` on macOS — verify CoreAudio device discovery
- Test `headmatch list-targets` — verify device listing
- Test `headmatch measure` with real headphones + mic on macOS
- Verify alignment code handles sounddevice latency characteristics
- Test GUI on macOS (tkinter ships with Python, but verify layout)
- Test offline workflow (prepare + fit) on macOS
- Verify config/cache paths land in ~/Library/
- Update README.md with macOS installation instructions
- Update CHANGELOG.md and cut release

## Out of scope
- Windows testing
- CI matrix for macOS (can be a follow-up)

## Acceptance criteria
- One successful end-to-end measurement on macOS hardware
- GUI launches and all views render correctly
- README includes macOS section
- Release tagged

## Suggested files
- `README.md`
- `CHANGELOG.md`
- `docs/releases/X.Y.Z.md`

## Priority
High — gates the macOS release, but depends on TASK-087 completion.
