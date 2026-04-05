# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for HeadMatch GUI — Linux x64 single-file binary.

Build with:  pyinstaller headmatch.spec
Or use:      python scripts/build.py
"""

import os
import sys
from pathlib import Path

block_cipher = None

# ── Collect BLAS/LAPACK shared libraries from numpy/scipy ──
# pip-installed wheels bundle their own OpenBLAS in .libs directories.
# PyInstaller's hooks usually find these, but we add them explicitly
# as a safety net for cross-distro compatibility.

_blas_libs = []

for pkg_name in ('numpy', 'scipy'):
    try:
        pkg = __import__(pkg_name)
        pkg_dir = os.path.dirname(pkg.__file__)
        # Check .libs directory (pip wheel layout)
        libs_dir = os.path.join(pkg_dir, '.libs')
        if os.path.isdir(libs_dir):
            for f in os.listdir(libs_dir):
                full = os.path.join(libs_dir, f)
                if os.path.isfile(full) and ('.so' in f or '.dylib' in f):
                    _blas_libs.append((full, '.'))
        # Also check for .so files directly in the package (some builds)
        for root, _dirs, files in os.walk(pkg_dir):
            for f in files:
                if ('openblas' in f.lower() or 'lapack' in f.lower()) and ('.so' in f or '.dylib' in f):
                    full = os.path.join(root, f)
                    if os.path.isfile(full):
                        _blas_libs.append((full, '.'))
    except ImportError:
        pass

# Deduplicate by basename
_seen = set()
_deduped = []
for src, dst in _blas_libs:
    name = os.path.basename(src)
    if name not in _seen:
        _seen.add(name)
        _deduped.append((src, dst))
_blas_libs = _deduped

print(f"Bundling {len(_blas_libs)} BLAS/LAPACK libraries from pip packages")
for src, _ in _blas_libs:
    print(f"  {src}")



# Collect example target CSVs as data files
example_targets = []
targets_dir = os.path.join('docs', 'examples', 'targets')
if os.path.isdir(targets_dir):
    for f in os.listdir(targets_dir):
        if f.endswith('.csv'):
            example_targets.append(
                (os.path.join(targets_dir, f), os.path.join('docs', 'examples', 'targets'))
            )

a = Analysis(
    ['scripts/entry_gui.py'],
    pathex=['.'],
    binaries=_blas_libs,
    datas=example_targets,
    hiddenimports=[
        'headmatch',
        'headmatch.cli',
        'headmatch.gui',
        'headmatch.gui_views',
        'headmatch.audio_backend',
        'headmatch.backend_pipewire',
        'headmatch.measure',
        'headmatch.pipeline',
        'headmatch.pipeline_artifacts',
        'headmatch.pipeline_confidence',
        'headmatch.analysis',
        'headmatch.peq',
        'headmatch.signals',
        'headmatch.targets',
        'headmatch.target_editor',
        'headmatch.exporters',
        'headmatch.plots',
        'headmatch.io_utils',
        'headmatch.settings',
        'headmatch.contracts',
        'headmatch.paths',
        'headmatch.history',
        'headmatch.app_identity',
        'headmatch.apo_import',
        'headmatch.apo_refine',
        'headmatch.headphone_db',
        'headmatch.desktop',
        'headmatch.troubleshooting',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Exclude sounddevice — Linux uses PipeWire, not PortAudio
    excludes=['sounddevice', 'matplotlib', 'IPython', 'notebook', 'pytest'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='headmatch-gui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI app — no terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)


# ── CLI binary ──

cli_a = Analysis(
    ['scripts/entry_cli.py'],
    pathex=['.'],
    binaries=_blas_libs,
    datas=example_targets,
    hiddenimports=[
        'headmatch',
        'headmatch.cli',
        'headmatch.audio_backend',
        'headmatch.backend_pipewire',
        'headmatch.measure',
        'headmatch.pipeline',
        'headmatch.pipeline_artifacts',
        'headmatch.pipeline_confidence',
        'headmatch.analysis',
        'headmatch.peq',
        'headmatch.signals',
        'headmatch.targets',
        'headmatch.target_editor',
        'headmatch.exporters',
        'headmatch.plots',
        'headmatch.io_utils',
        'headmatch.settings',
        'headmatch.contracts',
        'headmatch.paths',
        'headmatch.history',
        'headmatch.app_identity',
        'headmatch.apo_import',
        'headmatch.apo_refine',
        'headmatch.headphone_db',
        'headmatch.desktop',
        'headmatch.troubleshooting',
        'headmatch.tui',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['sounddevice', 'matplotlib', 'IPython', 'notebook', 'pytest'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

cli_pyz = PYZ(cli_a.pure, cli_a.zipped_data, cipher=block_cipher)

cli_exe = EXE(
    cli_pyz,
    cli_a.scripts,
    cli_a.binaries,
    cli_a.zipfiles,
    cli_a.datas,
    [],
    name='headmatch',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # CLI needs terminal
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
