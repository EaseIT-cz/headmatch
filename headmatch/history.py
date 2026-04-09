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
class RunComparisonField:
    label: str
    left: str
    right: str


@dataclass(frozen=True)
class RunHistoryComparison:
    left_entry: RunHistoryEntry
    right_entry: RunHistoryEntry
    fields: tuple[RunComparisonField, ...]


@dataclass(frozen=True)
class HistorySelection:
    search_root: str
    selected_summary: str | None
    selected_guide: str | None
    selected_entry: RunHistoryEntry | None
    comparison: RunHistoryComparison | None
    items: tuple[RunHistoryEntry, ...]


def _iter_summary_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return ()
    return root.rglob('run_summary.json')


def load_recent_runs(root: str | Path, *, limit: int = 10) -> list[RunHistoryEntry]:
    root_path = Path(root).expanduser()
    entries: list[RunHistoryEntry] = []
    for summary_path in sorted(
        _iter_summary_files(root_path),
        key=lambda p: (p.stat().st_mtime_ns, str(p.parent), str(p)),
        reverse=True,
    ):
        try:
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
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


def _format_predicted_error(summary: FrontendRunSummary) -> str:
    error = summary.predicted_error_db
    return f"L rms {error.left_rms:.2f}, R rms {error.right_rms:.2f}, L max {error.left_max:.2f}, R max {error.right_max:.2f} dB"


def _format_confidence(summary: FrontendRunSummary) -> str:
    confidence = summary.confidence
    return f"{confidence.label.title()} ({confidence.score}/100) — {confidence.headline}"


def build_run_comparison(entries: tuple[RunHistoryEntry, ...] | list[RunHistoryEntry]) -> RunHistoryComparison | None:
    if len(entries) < 2:
        return None
    left_entry = entries[0]
    right_entry = entries[1]
    left = left_entry.summary
    right = right_entry.summary
    return RunHistoryComparison(
        left_entry=left_entry,
        right_entry=right_entry,
        fields=(
            RunComparisonField("Target", left.target, right.target),
            RunComparisonField("Kind", left.kind, right.kind),
            RunComparisonField("Sample rate", f"{left.sample_rate} Hz", f"{right.sample_rate} Hz"),
            RunComparisonField("Filters (L/R)", f"{left.filters.left}/{left.filters.right}", f"{right.filters.left}/{right.filters.right}"),
            RunComparisonField("Predicted error", _format_predicted_error(left), _format_predicted_error(right)),
            RunComparisonField("Confidence", _format_confidence(left), _format_confidence(right)),
            RunComparisonField("Interpretation", left.confidence.interpretation or "—", right.confidence.interpretation or "—"),
            RunComparisonField(
                "Warnings",
                "; ".join(left.confidence.warnings[:3]) or "None",
                "; ".join(right.confidence.warnings[:3]) or "None",
            ),
        ),
    )


def read_results_guide(path: str | Path) -> str:
    guide_path = Path(path).expanduser()
    if not guide_path.exists():
        return 'Results guide not found. Open run_summary.json in the same folder for the machine-readable overview.'
    return guide_path.read_text(encoding="utf-8")


def build_history_selection(search_root: str | Path, config_root: str | Path | None = None, *, limit: int = 10) -> HistorySelection:
    root = Path(search_root).expanduser()
    entries = load_recent_runs(root, limit=limit)
    selected_entry = entries[0] if entries else None
    selected_summary = str(selected_entry.summary_path) if selected_entry else None
    selected_guide = read_results_guide(selected_entry.guide_path) if selected_entry else None
    return HistorySelection(
        search_root=str(root),
        selected_summary=selected_summary,
        selected_guide=selected_guide,
        selected_entry=selected_entry,
        comparison=build_run_comparison(entries),
        items=tuple(entries),
    )


# ── Display helpers ──

_CONFIDENCE_ICONS = {
    "high": "\u2713",   # ✓
    "medium": "\u26A0", # ⚠
    "low": "\u2717",    # ✗
}


def confidence_icon(label: str) -> str:
    """Return a Unicode icon for the confidence level."""
    return _CONFIDENCE_ICONS.get(label, "?")


def format_run_entry(entry: RunHistoryEntry, index: int) -> str:
    """Format a single run entry for CLI display."""
    s = entry.summary
    conf = s.confidence
    icon = confidence_icon(conf.label)
    err = s.predicted_error_db
    lines = [
        f"  {index}) {icon} [{conf.label.upper():>6s} {conf.score:3d}/100] {s.kind}",
        f"     folder: {s.out_dir}",
        f"     target: {s.target}  filters: L={s.filters.left} R={s.filters.right}",
        f"     error:  L rms={err.left_rms:.2f}  R rms={err.right_rms:.2f}  "
        f"L max={err.left_max:.2f}  R max={err.right_max:.2f} dB",
    ]
    if conf.headline:
        lines.append(f"     note:   {conf.headline}")
    return "\n".join(lines)


def format_comparison_table(comparison: RunHistoryComparison) -> str:
    """Format a comparison table for CLI display."""
    lines = [
        "Side-by-side comparison",
        "=" * 60,
        f"  A: {comparison.left_entry.summary.out_dir}",
        f"  B: {comparison.right_entry.summary.out_dir}",
        "",
    ]
    max_label = max(len(f.label) for f in comparison.fields)
    for field in comparison.fields:
        lines.append(f"  {field.label:<{max_label}s}  A: {field.left}")
        lines.append(f"  {' ':<{max_label}s}  B: {field.right}")
        lines.append("")
    return "\n".join(lines)
