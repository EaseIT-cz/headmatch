"""Parse Equalizer APO parametric EQ presets into PEQBand lists."""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple

from .peq import PEQBand


_APO_FILTER_RE = re.compile(
    r'Filter\s+\d+:\s+ON\s+(\w+)\s+'
    r'Fc\s+([\d.]+)\s*Hz\s+'
    r'Gain\s+([-\d.]+)\s*dB\s+'
    r'Q\s+([\d.]+)',
    re.IGNORECASE,
)

_APO_TYPE_MAP = {
    'PK': 'peaking',
    'PEQ': 'peaking',
    'PEAKING': 'peaking',
    'LS': 'lowshelf',
    'LOWSHELF': 'lowshelf',
    'LSC': 'lowshelf',
    'HS': 'highshelf',
    'HIGHSHELF': 'highshelf',
    'HSC': 'highshelf',
}


def parse_apo_parametric(text: str) -> Tuple[List[PEQBand], List[PEQBand]]:
    """Parse an Equalizer APO parametric preset into (left_bands, right_bands).

    If the preset has per-channel sections (Channel: L / Channel: R), bands are
    split accordingly. If no channel markers are found, all bands are returned
    in both lists (mono preset applied to both channels).
    """
    lines = text.splitlines()
    left: List[PEQBand] = []
    right: List[PEQBand] = []
    current_channel = 'both'

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith(';'):
            continue

        # Channel marker
        channel_match = re.match(r'Channel:\s*(\w+)', stripped, re.IGNORECASE)
        if channel_match:
            ch = channel_match.group(1).upper()
            if ch in ('L', 'LEFT', '1'):
                current_channel = 'left'
            elif ch in ('R', 'RIGHT', '2'):
                current_channel = 'right'
            else:
                current_channel = 'both'
            continue

        # Filter line
        m = _APO_FILTER_RE.search(stripped)
        if not m:
            continue

        kind_raw = m.group(1).upper()
        kind = _APO_TYPE_MAP.get(kind_raw)
        if kind is None:
            continue

        q_val = float(m.group(4))
        band = PEQBand(
            kind=kind,
            freq=float(m.group(2)),
            gain_db=float(m.group(3)),
            q=q_val,
            slope=q_val if kind in ("lowshelf", "highshelf") else None,
        )

        if current_channel == 'left':
            left.append(band)
        elif current_channel == 'right':
            right.append(band)
        else:
            left.append(band)
            right.append(band)

    return left, right


def load_apo_preset(path: str | Path) -> Tuple[List[PEQBand], List[PEQBand]]:
    """Load an Equalizer APO .txt preset file."""
    return parse_apo_parametric(Path(path).read_text(encoding="utf-8"))
