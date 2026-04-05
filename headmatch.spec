# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for HeadMatch GUI — Linux x64 single-file binary.

Build with:  pyinstaller headmatch.spec
Or use:      python scripts/build.py
"""

import os
import sys
from pathlib import Path

block_cipher = None

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
    ['headmatch/gui.py'],
    pathex=['.'],
    binaries=[],
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
