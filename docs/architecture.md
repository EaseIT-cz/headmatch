# headmatch architecture

## Product intent

`headmatch` is a beginner-friendly headphone measurement and EQ toolkit for audiophiles and audio enthusiasts.

Primary product goals:
- make headphone measurement feel simple and guided
- support both automatic Linux/PipeWire capture and offline recorder-first workflows
- generate conservative EQ that improves tonality without chasing tiny measurement artifacts
- support headphone cloning from measurements or published FR CSVs
- keep outputs understandable for non-technical users

## Audience assumptions

The primary audience is not technical.
They want:
- a clear starting point
- minimal configuration
- visible progress
- stable, repeatable results
- safe defaults
- readable output files and presets

Design implication: the system should prefer opinionated workflows over flexibility-first APIs.

## Current system shape

### Core pipeline

1. generate a log sweep
2. play and record it, or prepare an offline package
3. align the recording to the reference sweep
4. estimate left/right frequency response
5. normalize at 1 kHz
6. smooth measurement curves
7. fit conservative PEQ bands
8. export CamillaDSP YAML
9. optionally repeat in an iterative loop

### Modules

- `signals.py`
  - sweep generation
  - smoothing helpers
  - frequency grid helpers
- `measure.py`
  - render sweep WAV
  - PipeWire-based measurement
  - offline measurement package generation
- `analysis.py`
  - recording alignment
  - FR estimation
  - measurement CSV export
- `targets.py`
  - target curve loading and normalization
  - clone target generation
- `peq.py`
  - RBJ biquad modeling
  - greedy PEQ fitting
- `exporters.py`
  - CamillaDSP YAML export
- `pipeline.py`
  - measurement-to-fit orchestration
  - iterative measurement loop
- `cli.py`
  - command-line entry points

## Architecture decisions

### 1. Opinionated workflows over generic primitives

The repo already exposes low-level pieces, but the product should behave like a guided tool.

Implication:
- keep the CLI simple and prescriptive
- prefer a few named workflows over many knobs
- hide advanced controls unless they materially improve success rate

### 2. Two capture modes, one mental model

The product should present one measurement concept with two capture implementations:
- online: PipeWire playback/recording
- offline: recorder-first workflow with later import

Implication:
- the UI/CLI should surface a single “measure” story
- offline mode should feel like a fallback, not a separate product

### 3. Conservative EQ is a feature

For headphone users, small resonant fixes are less important than not making things worse.

Implication:
- limit filter count
- clamp gain and Q
- bias toward broad tonal correction
- avoid overfitting treble noise

### 4. Cloning is a target-generation step, not a separate fitting engine

A clone curve should simply produce a target delta curve that can be fed back into the normal fit pipeline.

Implication:
- keep clone generation as a curve transformation
- keep fitting logic centralized

### 5. File outputs must be understandable

The audience should be able to open folders and understand what happened.

Implication:
- predictable output names
- clear metadata files
- readable summaries and reports
- avoid deeply nested or cryptic artifacts

## Current constraints / risks

- The measurement math is still relatively simple and may need refinement for real-world recordings.
- PipeWire device handling is likely the most fragile integration point.
- The current export surface is useful, but a beginner-friendly orchestration layer is still missing.
- The current codebase has good building blocks, but the product experience is not yet fully shaped around non-technical users.

## Recommended near-term direction

Build around three layers:

1. **workflow layer**
   - opinionated user journeys
   - guided capture and fit
   - beginner-oriented summaries

2. **domain layer**
   - measurement analysis
   - target curve handling
   - EQ fitting
   - clone curve generation

3. **integration layer**
   - PipeWire
   - CamillaDSP
   - file system outputs
   - recorder import/export

### 7. Versioning must be visible everywhere

Users should always be able to tell what version they are running.

Implication:
- keep one canonical in-package version source (`headmatch.app_identity`)
- expose version in CLI, TUI, and future GUI entry points
- include version in generated outputs
- prefer semantic versions with optional build metadata

## Future product direction

If the repo grows, the likely next step is a small guided app or wizard-like CLI that reduces the number of choices exposed to the user at once.

The right shape for this audience is not “more options.” It is “fewer ways to get lost.”
