#!/usr/bin/env python3
"""Build HeadMatch GUI as a single-file binary using PyInstaller.

Usage:
    python scripts/build.py [--clean]

Produces: dist/headmatch-gui (Linux) or dist/headmatch-gui.exe (Windows)
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "headmatch.spec"
DIST = ROOT / "dist"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build HeadMatch GUI binary")
    parser.add_argument("--clean", action="store_true", help="Remove build/ and dist/ before building")
    args = parser.parse_args(argv)

    os.chdir(ROOT)

    if args.clean:
        for d in ("build", "dist"):
            p = ROOT / d
            if p.exists():
                print(f"Cleaning {p}")
                shutil.rmtree(p)

    # Verify PyInstaller is available
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller not found. Install with: pip install pyinstaller")
        sys.exit(1)

    # Verify headmatch is importable
    try:
        import headmatch
        print(f"Building HeadMatch {headmatch.__version__}")
    except ImportError:
        print("headmatch package not found. Install with: pip install -e .")
        sys.exit(1)

    # Check numpy BLAS source — pip wheels are preferred for portability
    try:
        import numpy as np
        np_dir = Path(np.__file__).parent
        libs_dir = np_dir / ".libs"
        if libs_dir.is_dir() and any(f for f in libs_dir.iterdir() if "openblas" in f.name.lower()):
            print(f"  numpy BLAS: bundled OpenBLAS in {libs_dir} ✓")
        else:
            print(f"  numpy BLAS: system library (binary may not be portable!)")
            print(f"  Tip: pip install numpy --force-reinstall to use the pip wheel with bundled OpenBLAS")
    except ImportError:
        pass

    # Run PyInstaller
    cmd = [sys.executable, "-m", "PyInstaller", str(SPEC), "--noconfirm"]
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode != 0:
        print("PyInstaller build failed.")
        sys.exit(1)

    # Find output binaries
    ext = ".exe" if sys.platform == "win32" else ""
    binaries = {
        "headmatch-gui": DIST / f"headmatch-gui{ext}",
        "headmatch": DIST / f"headmatch{ext}",
    }

    print("\nBuild results:")
    all_ok = True
    for name, path in binaries.items():
        if path.exists():
            size_mb = path.stat().st_size / (1024 * 1024)
            print(f"  ✓ {name}: {path} ({size_mb:.1f} MB)")
        else:
            print(f"  ✗ {name}: NOT FOUND at {path}")
            all_ok = False

    if not all_ok:
        print("\nSome binaries were not produced.")
        sys.exit(1)

    # Smoke test CLI with --version
    cli_binary = binaries["headmatch"]
    print(f"\nSmoke test: {cli_binary.name} --version ...")
    smoke = subprocess.run(
        [str(cli_binary), "--version"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if smoke.returncode == 0:
        print(f"  {smoke.stdout.strip()}")
    else:
        print(f"  Returned {smoke.returncode}: {(smoke.stderr or '')[:300]}")

    print(f"\nDone. Distribute:")
    for name, path in binaries.items():
        print(f"  {path}")


if __name__ == "__main__":
    main()
