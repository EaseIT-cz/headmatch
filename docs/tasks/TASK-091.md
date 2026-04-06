# TASK-091: PyInstaller spec and build script for Linux x64

## Summary
Create a working PyInstaller spec and build script for building Linux x64 binaries.

## Context
The current spec (`headmatch.spec`) is a good starting point, but the build fails locally because the sandbox Python doesn't have a shared library (`libpython3.11.so.1.0`). The GitHub Actions workflow installs `python3-tk` via apt before building, which provides a Python with shared library.

**Status: Blocked — waiting for human to prepare host environment.**

## Blockers

The host/sandbox needs these system packages to build a working PyInstaller binary:

```bash
sudo apt-get update
sudo apt-get install -y \
    python3-tk \
    python3-dev \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6
```

> 💡 `python3-tk` is critical — it provides `libpython3.11.so.1.0` (or equivalent for your distro), which is required for PyInstaller to embed Python.

## Human requirements (after blocker is resolved)

### Step 1: Set up the build venv

```bash
python3 -m venv .venv-build
. .venv-build/bin/activate

pip install --upgrade pip
pip install pyinstaller numpy scipy
```

### Step 2: Identify missing resources

From the GUI, copy the following to the repo and update `.spec`:

| Resource type | Search for | Example |
|---------------|------------|---------|
| Icons | `PhotoImage`, `bitmap`, `icon` | `audio-headphones` (system theme) |
| View templates | `.json`, `.yaml`, `.csv` | `docs/examples/targets/flat.csv` |
| Data files | `open(...)`, `load(...)`, `read_csv` | `example_targets/*.csv` |

### Step 3: Update `headmatch.spec`

Add missing data files to the `datas=` list in the spec:

```python
# Example: add all CSV and JSON in docs/examples
datas=[
    (os.path.join('docs', 'examples'), os.path.join('docs', 'examples')),
    # Add any GUI templates/data files here
],
```

### Step 4: Test the build

```bash
cd /shared/headmatch
. .venv-build/bin/activate
python scripts/build.py --clean
```

### Step 5: Validate the binary

```bash
# Test CLI entry point
./dist/headmatch --help

# Test GUI (should show main window)
./dist/headmatch-gui
```

## Scope

- ✅ Create/Update `headmatch.spec` with complete `datas=` list
- ✅ Create `scripts/build.py` flag (`--binary`) that uses spec
- ✅ Verify binary runs on a clean Linux VM (same distro/version as CI runners)

## Out-of-scope

- Building macOS `.app` or Windows `.exe` — those are separate tasks
- AppImage or Flatpak — not part of this release

## Acceptance criteria

1. `python scripts/build.py --clean --binary` succeeds without errors
2. Built binary runs on a clean Linux environment:
   - CLI (`headmatch --help`) works
   - GUI (`headmatch-gui`) shows main window without import errors
3. No missing file/resource errors in terminal output
4. Binary size < 100 MB (reasonable for one-file PyInstaller)

## Suggested files/components

- `headmatch.spec`
- `scripts/build.py`
- `headmatch/gui.py`
- `docs/examples/` (CSV, JSON, desktop files)
