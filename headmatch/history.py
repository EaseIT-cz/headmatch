from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .contracts import FrontendRunSummary


@dataclass(frozen=True)
class RunHistoryEntry:
    summary_path: Path
    summary: FrontendRunSummary
    guide_path: Path


@dataclass(frozen=True)
class HistorySelection:
    search_root: str
    selected_summary: str | None
    selected_guide: str | None
    items: tuple[tuple[str, str, str], ...]


def _iter_summary_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return ()
    return root.rglob('run_summary.json')


def load_recent_runs(root: str | Path, *, limit: int = 10) -> list[RunHistoryEntry]:
    root_path = Path(root).expanduser()
    entries: list[RunHistoryEntry] = []
    for summary_path in sorted(_iter_summary_files(root_path), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            payload = json.loads(summary_path.read_text())
            summary = FrontendRunSummary.from_dict(payload)
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
        guide_path = Path(summary.results_guide)
        if not guide_path.is_absolute():
            guide_path = (summary_path.parent / guide_path).resolve()
        entries.append(RunHistoryEntry(summary_path=summary_path, summary=summary, guide_path=guide_path))
        if len(entries) >= limit:
            break
    return entries


def read_results_guide(path: str | Path) -> str:
    guide_path = Path(path).expanduser()
    if not guide_path.exists():
        return 'Results guide not found. Open run_summary.json in the same folder for the machine-readable overview.'
    return guide_path.read_text()


def build_history_selection(search_root: str | Path, config_root: str | Path | None = None, *, limit: int = 10) -> HistorySelection:
    root = Path(search_root).expanduser()
    entries = load_recent_runs(root, limit=limit)
    items: list[tuple[str, str, str]] = []
    selected_summary = None
    selected_guide = None
    for entry in entries:
        label = entry.summary.out_dir
        details = f"{entry.summary.kind} | {entry.summary.target} | {entry.summary.sample_rate} Hz"
        items.append((str(entry.summary_path.parent), label, details))
    if entries:
        selected_summary = str(entries[0].summary_path)
        selected_guide = read_results_guide(entries[0].guide_path)
    return HistorySelection(search_root=str(root), selected_summary=selected_summary, selected_guide=selected_guide, items=tuple(items))
