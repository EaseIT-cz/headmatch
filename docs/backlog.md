# headmatch backlog

Priority is ordered top to bottom.

## P0 — configuration and interaction foundation

1. [done] Implement config persistence/loading against the shared interaction contract, including PipeWire target preload.
2. [done] Add a default config file location strategy plus first-run creation behavior.
3. [done] Expose a lightweight settings API usable by CLI, TUI, and GUI.

## P1 — GUI and TUI core workflows

4. [done] Implement the initial TUI wizard for beginner-guided measurement and fit.
5. Implement the GUI skeleton and main navigation flow.
6. [done] Preload shared saved config values in the TUI and shared frontend helpers.
7. [done] Add a run/history browser in the TUI plus shared history-loading helpers using `run_summary.json` as the stable summary source.

## P1 — remaining product polish

8. [done] Improve output folder discoverability further, including a short README section that explains what each generated file means.
9. [done] Add a documented install and first-run path for Linux users.
10. [done] Package example configs and sample data.

## P2 — capture and analysis robustness

11. Improve PipeWire node selection and recording/playback coordination.
12. Make offline measurement import more tolerant of real recorder files.
13. Strengthen alignment and sweep detection for noisy or delayed recordings.
14. Add more synthetic tests for left/right imbalance, noise, and delay.

## P2 — EQ fitting and export polish

15. Refine PEQ fitting heuristics for safer shelf selection and fewer narrow corrections.
16. Improve CamillaDSP export templates for real-world setups.
17. Add export formats beyond CamillaDSP only if there is an immediate user need.

## P2 — target curves and cloning follow-up

18. Add example clone targets and documentation for common headphone pairs.
19. Validate clone curve generation against multiple curve sources.
20. Expand target curve loading to handle more CSV layouts safely if new formats appear in the wild.
