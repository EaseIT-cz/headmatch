# headmatch backlog

Priority is ordered top to bottom.

## P0 — product clarity and beginner workflow

1. Improve output folder structure and generated metadata so non-technical users can understand results.
2. Add clearer validation/error messages for missing devices, bad sample rates, and unsupported recordings.
3. Expand target curve loading to handle more CSV layouts safely.
4. Add example clone targets and documentation for common headphone pairs.
5. Validate clone curve generation against multiple curve sources.

## P1 — capture and analysis robustness

6. Improve PipeWire node selection and recording/playback coordination.
7. Make offline measurement import more tolerant of real recorder files.
8. Strengthen alignment and sweep detection for noisy or delayed recordings.
9. Add more synthetic tests for left/right imbalance, noise, and delay.

## P1 — target curves and cloning

6. Expand target curve loading to handle more CSV layouts safely.
7. Add example clone targets and documentation for common headphone pairs.
8. Validate clone curve generation against multiple curve sources.

## P2 — EQ fitting and export polish

9. Refine PEQ fitting heuristics for safer shelf selection and fewer narrow corrections.
10. Improve CamillaDSP export templates for real-world setups.
11. Add export formats beyond CamillaDSP only if there is an immediate user need.

## P2 — packaging and distribution

12. Add a documented install and first-run path for Linux users.
13. Package example configs and sample data.
14. Consider a small guided UI once the CLI flow is stable.
