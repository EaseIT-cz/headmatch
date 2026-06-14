"""Built-in tonal target curves selectable in advanced mode.

These are compact, illustrative *absolute* tonal targets (normalised at 1 kHz).
They are intended as convenient starting points layered on top of the hearing
compensation; a user can still browse to any custom target CSV. Curves mirror
the example CSVs in docs/examples/targets/.
"""
from __future__ import annotations

from pathlib import Path

# name -> (display label, [(freq_hz, target_db), ...])  -- absolute semantics, 1 kHz = 0
BUILTIN_TARGET_DEFS: dict[str, tuple[str, list[tuple[float, float]]]] = {
    "flat": ("Flat (default)", [
        (20, 0.0), (50, 0.0), (100, 0.0), (200, 0.0), (500, 0.0), (1000, 0.0),
        (2000, 0.0), (3000, 0.0), (6000, 0.0), (10000, 0.0), (16000, 0.0), (20000, 0.0),
    ]),
    "harman": ("Harman", [
        (20, 6.0), (50, 5.0), (100, 3.5), (200, 2.0), (500, 0.8), (1000, 0.0),
        (2000, 1.2), (3000, 2.0), (6000, 0.5), (10000, -1.0), (16000, -2.2), (20000, -3.0),
    ]),
    "free_field": ("Free field", [
        (20, -0.6), (50, -0.4), (100, -0.2), (200, 0.0), (500, 0.3), (1000, 0.0),
        (2000, 1.5), (3000, 2.2), (6000, 1.0), (10000, 0.0), (16000, -0.6), (20000, -1.0),
    ]),
    "diffuse_field": ("Diffuse field", [
        (20, -1.0), (50, -0.8), (100, -0.4), (200, 0.0), (500, 0.6), (1000, 0.0),
        (2000, 2.2), (3000, 3.2), (6000, 1.5), (10000, 0.2), (16000, -0.8), (20000, -1.2),
    ]),
}

# "flat" needs no target file (it is the default no-op target).
SELECTABLE_TARGET_NAMES = [name for name in BUILTIN_TARGET_DEFS if name != "flat"]


def builtin_target_label(name: str) -> str:
    return BUILTIN_TARGET_DEFS[name][0]


def label_to_name(label: str) -> str | None:
    """Map a display label back to its built-in name (None for flat/unknown)."""
    for name, (lbl, _pts) in BUILTIN_TARGET_DEFS.items():
        if lbl == label:
            return None if name == "flat" else name
    return None


def materialize_builtin_target(name: str, dest_dir: str | Path) -> Path:
    """Write a built-in target curve to ``dest_dir/<name>_target.csv`` and return it."""
    if name not in BUILTIN_TARGET_DEFS:
        raise KeyError(f"unknown built-in target: {name}")
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / f"{name}_target.csv"
    lines = ["frequency_hz,target_db"]
    lines += [f"{int(freq)},{db}" for freq, db in BUILTIN_TARGET_DEFS[name][1]]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
