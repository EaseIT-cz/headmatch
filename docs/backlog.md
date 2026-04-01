# headmatch backlog

Priority is ordered top to bottom.

## P0 — product clarity and beginner workflow

1. Define the guided user journey and the exact wording for each step.
2. Add a beginner-first CLI layer that exposes one obvious path for:
   - measure
   - analyze offline recording
   - fit EQ
   - export CamillaDSP preset
3. Improve output folder structure and generated metadata so non-technical users can understand results.
4. Add clearer validation/error messages for missing devices, bad sample rates, and unsupported recordings.
5. Add a concise “what to do next” summary after each command.

## P1 — capture and analysis robustness

6. Improve PipeWire node selection and recording/playback coordination.
7. Make offline measurement import more tolerant of real recorder files.
8. Strengthen alignment and sweep detection for noisy or delayed recordings.
9. Add more synthetic tests for left/right imbalance, noise, and delay.

## P1 — target curves and cloning

10. Expand target curve loading to handle more CSV layouts safely.
11. Add example clone targets and documentation for common headphone pairs.
12. Validate clone curve generation against multiple curve sources.

## P2 — EQ fitting and export polish

13. Refine PEQ fitting heuristics for safer shelf selection and fewer narrow corrections.
14. Improve CamillaDSP export templates for real-world setups.
15. Add export formats beyond CamillaDSP only if there is an immediate user need.

## P2 — packaging and distribution

16. Add a documented install and first-run path for Linux users.
17. Package example configs and sample data.
18. Consider a small guided UI once the CLI flow is stable.
