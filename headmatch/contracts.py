from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, Optional

from .signals import SweepSpec

CONFIG_SCHEMA_VERSION = 1
RUN_SUMMARY_SCHEMA_VERSION = 1

WorkflowName = Literal[
    "start",
    "measure",
    "prepare-offline",
    "analyze",
    "fit",
    "fit-offline",
    "iterate",
    "clone-target",
]

RunMode = Literal["online", "offline", "analysis-only", "clone-target"]


@dataclass
class FrontendConfig:
    """Persisted user-facing settings shared by CLI, TUI, and GUI."""

    schema_version: int = CONFIG_SCHEMA_VERSION
    default_output_dir: Optional[str] = None
    preferred_target_csv: Optional[str] = None
    pipewire_output_target: Optional[str] = None
    pipewire_input_target: Optional[str] = None
    sample_rate: int = 48000
    duration_s: float = 8.0
    f_start_hz: float = 20.0
    f_end_hz: float = 22000.0
    pre_silence_s: float = 0.5
    post_silence_s: float = 1.0
    amplitude: float = 0.2
    max_filters: int = 8
    start_iterations: int = 1
    iterate_iterations: int = 2

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FrontendRunRequest:
    """Shared request payload from a frontend into the domain pipeline."""

    workflow: WorkflowName
    mode: RunMode
    output_dir: Optional[str] = None
    recording_path: Optional[str] = None
    target_csv: Optional[str] = None
    output_target: Optional[str] = None
    input_target: Optional[str] = None
    notes: str = ""
    max_filters: int = 8
    iterations: int = 1
    source_csv: Optional[str] = None
    clone_target_csv: Optional[str] = None
    clone_out: Optional[str] = None
    sweep: Optional[SweepSpec] = None

    def to_dict(self) -> dict:
        payload = asdict(self)
        if self.sweep is not None:
            payload["sweep"] = asdict(self.sweep)
        return payload


@dataclass
class FrontendRunSummary:
    """Minimal stable summary that every frontend can read back."""

    schema_version: int
    kind: Literal["fit", "iteration"]
    out_dir: str
    sample_rate: int
    frequency_points: int
    target: str
    filters: dict
    predicted_error_db: dict
    results_guide: str

    @classmethod
    def from_dict(cls, payload: dict) -> "FrontendRunSummary":
        return cls(
            schema_version=int(payload.get("schema_version", RUN_SUMMARY_SCHEMA_VERSION)),
            kind=payload["kind"],
            out_dir=payload["out_dir"],
            sample_rate=int(payload["sample_rate"]),
            frequency_points=int(payload["frequency_points"]),
            target=payload["target"],
            filters=dict(payload["filters"]),
            predicted_error_db=dict(payload["predicted_error_db"]),
            results_guide=payload.get("results_guide", str(Path(payload["out_dir"]) / "README.txt")),
        )
