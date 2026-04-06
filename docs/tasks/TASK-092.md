# TASK-092: macOS binary distribution (PyInstaller)

**Status**: Completed (2026-04-06)

**Summary**: Add macOS binary build to GitHub Actions workflow.

**Implementation**:
- Added build-macos job to .github/workflows/release-binary.yml
- Uses runs-on: macos-latest
- Pins numpy<2 and scipy<1.14 for consistent OpenBLAS behavior
- Produces headmatch-gui-macos-x64 and headmatch-macos-x64 binaries
- Attaches binaries to GitHub releases on version tags

**Files Modified**:
- .github/workflows/release-binary.yml
