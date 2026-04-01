# headmatch backlog

Priority is ordered top to bottom.

## Active

### P2 — capture and analysis robustness

1. Improve PipeWire node selection and recording/playback coordination.
2. Make offline measurement import more tolerant of real recorder files.
3. Strengthen alignment and sweep detection for noisy or delayed recordings.
4. Add more synthetic tests for left/right imbalance, noise, and delay.

### P2 — EQ fitting and export polish

5. Refine PEQ fitting heuristics for safer shelf selection and fewer narrow corrections.
6. Improve CamillaDSP export templates for real-world setups.
7. Add export formats beyond CamillaDSP only if there is an immediate user need.

### P2 — target curves and cloning follow-up

8. Add example clone targets and documentation for common headphone pairs.
9. Validate clone curve generation against multiple curve sources.
10. Expand target curve loading to handle more CSV layouts safely if new formats appear in the wild.

## Completed recently

- Beginner-first CLI workflow
- Versioning and app identity
- Shared frontend interaction contract
- Shared settings persistence and preload
- Initial TUI wizard
- TUI run/history browsing
- GUI shell and navigation
- GUI measurement wizard for online and offline flows
- Shared TUI/GUI history browsing
- Output-folder guides and first-run docs
- Packaged config/example documentation
