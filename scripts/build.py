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

    # Run PyInstaller
    cmd = [sys.executable, "-m", "PyInstaller", str(SPEC), "--noconfirm"]
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode != 0:
        print("PyInstaller build failed.")
        sys.exit(1)

    # Find the output binary
    binary_name = "headmatch-gui.exe" if sys.platform == "win32" else "headmatch-gui"
    binary = DIST / binary_name
    if not binary.exists():
        print(f"Expected output not found: {binary}")
        sys.exit(1)

    size_mb = binary.stat().st_size / (1024 * 1024)
    print(f"\nBuild successful!")
    print(f"  Output: {binary}")
    print(f"  Size:   {size_mb:.1f} MB")

    # Smoke test: --help should work
    print("\nSmoke test: running --help...")
    smoke = subprocess.run(
        [str(binary), "--help"],
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "DISPLAY": os.environ.get("DISPLAY", "")},
    )
    if smoke.returncode == 0:
        print("  Smoke test passed.")
    else:
        # --help may fail without display; check if it's a TclError
        stderr = smoke.stderr or ""
        if "TclError" in stderr or "no display" in stderr.lower():
            print("  Smoke test: binary runs but no display available (expected in CI).")
        else:
            print(f"  Smoke test returned {smoke.returncode}")
            if smoke.stderr:
                print(f"  stderr: {smoke.stderr[:500]}")

    print(f"\nDone. Distribute: {binary}")


if __name__ == "__main__":
    main()
