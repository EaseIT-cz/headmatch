# headmatch backlog

Priority is ordered top to bottom.

## P1 — remaining product polish

1. Improve output folder discoverability further, including a short README section that explains what each generated file means.
2. Add a documented install and first-run path for Linux users.
3. Package example configs and sample data.
4. Consider a small guided UI once the CLI flow is stable.

## P1 — capture and analysis robustness

5. Improve PipeWire node selection and recording/playback coordination.
6. Make offline measurement import more tolerant of real recorder files.
7. Strengthen alignment and sweep detection for noisy or delayed recordings.
8. Add more synthetic tests for left/right imbalance, noise, and delay.

## P2 — EQ fitting and export polish

9. Refine PEQ fitting heuristics for safer shelf selection and fewer narrow corrections.
10. Improve CamillaDSP export templates for real-world setups.
11. Add export formats beyond CamillaDSP only if there is an immediate user need.

## P2 — target curves and cloning follow-up

12. Add example clone targets and documentation for common headphone pairs.
13. Validate clone curve generation against multiple curve sources.
14. Expand target curve loading to handle more CSV layouts safely if new formats appear in the wild.
