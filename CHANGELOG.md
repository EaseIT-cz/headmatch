## 0.2.2 (in development)

### Features
- **Fixed-band GraphicEQ export**: Added export of fixed-band GraphicEQ profiles (geq_10_band and geq_31_band) for Equalizer APO integration.
- **Fixed-band GraphicEQ fitting**: New fit mode that applies correction directly to the shared objective/residual layer using predefined GraphicEQ frequency points.
- **Exact-count PEQ mode**: The `exact_n` fill policy ensures exactly N filters are used when specified, enabling precise control over filter count for multi-peak targets.

### Improvements
- **Synthetic regression test coverage**: Expanded the synthetic integration test suite with focused tests for:
  - exact_n fill policy with multi-peaked targets
  - underfitting when target changes are minimal
  - clone target normalization behavior
  - GraphicEQ export edge cases (zero preamp values)
  - Fixed-band profile generation (10-band and 31-band)
  - CamillaDSP filter ordering and naming

### Documentation
- Updated `docs/architecture.md` to document fixed-band GraphicEQ support
- Updated `docs/backlog.md` to reflect completed tasks and new feature candidates
- Improved clarity around filter family vs. fill policy separation

### Technical details
- Backend contract remains stable; no breaking changes
- New fit mode `graphic_eq` now available for fixed-band fitting workflows
- Export formats: Equalizer APO parametric, Equalizer APO GraphicEQ, CamillaDSP YAML
- All existing export formats and workflows continue to work as before

