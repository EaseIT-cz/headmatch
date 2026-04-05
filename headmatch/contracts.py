from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Optional

from .signals import SweepSpec

if TYPE_CHECKING:
    from .peq import FilterBudget

CONFIG_SCHEMA_VERSION = 1
RUN_SUMMARY_SCHEMA_VERSION = 1

WorkflowName = Literal[
    "start",
    "measure",
    "prepare-offline",
    "analyze",
    "fit",
    "fit",
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


@dataclass(frozen=True)
class RunFilterCounts:
    left: int
    right: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class RunErrorSummary:
    left_rms: float
    right_rms: float
    left_max: float
    right_max: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ConfidenceSummary:
    score: int
    label: Literal["high", "medium", "low"]
    headline: str
    interpretation: str
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]
    metrics: dict[str, float]

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["reasons"] = list(self.reasons)
        payload["warnings"] = list(self.warnings)
        return payload


@dataclass(frozen=True)
class FrontendRunSummary:
    """Minimal stable summary that every frontend can read back."""

    schema_version: int
    kind: Literal["fit", "iteration"]
    out_dir: str
    sample_rate: int
    frequency_points: int
    target: str
    filters: RunFilterCounts
    predicted_error_db: RunErrorSummary
    generated_by: dict[str, Any]
    confidence: ConfidenceSummary
    plots: dict[str, str]
    results_guide: str
    filter_budget: "FilterBudget | None" = None

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "out_dir": self.out_dir,
            "sample_rate": self.sample_rate,
            "frequency_points": self.frequency_points,
            "target": self.target,
            "filters": self.filters.to_dict(),
            "predicted_error_db": self.predicted_error_db.to_dict(),
            "generated_by": self.generated_by,
            "confidence": self.confidence.to_dict(),
            "plots": self.plots,
            "results_guide": self.results_guide,
            "filter_budget": None if self.filter_budget is None else {
                "family": self.filter_budget.family,
                "max_filters": self.filter_budget.max_filters,
                "fill_policy": self.filter_budget.fill_policy,
                "profile": self.filter_budget.profile,
            },
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "FrontendRunSummary":
        confidence_payload = payload.get("confidence", {})
        filter_budget_payload = payload.get("filter_budget")
        filter_budget = None
        if isinstance(filter_budget_payload, dict):
            from .peq import FilterBudget
            filter_budget = FilterBudget(**filter_budget_payload)

        return cls(
            schema_version=int(payload.get("schema_version", RUN_SUMMARY_SCHEMA_VERSION)),
            kind=payload["kind"],
            out_dir=payload["out_dir"],
            sample_rate=int(payload["sample_rate"]),
            frequency_points=int(payload["frequency_points"]),
            target=payload["target"],
            filters=RunFilterCounts(**dict(payload["filters"])),
            predicted_error_db=RunErrorSummary(**dict(payload["predicted_error_db"])),
            generated_by=dict(payload.get("generated_by", {})),
            confidence=ConfidenceSummary(
                score=int(confidence_payload.get("score", 0)),
                label=confidence_payload.get("label", "low"),
                headline=confidence_payload.get("headline", ""),
                interpretation=confidence_payload.get("interpretation", ""),
                reasons=tuple(confidence_payload.get("reasons", ())),
                warnings=tuple(confidence_payload.get("warnings", ())),
                metrics=dict(confidence_payload.get("metrics", {})),
            ),
            plots=dict(payload.get("plots", {})),
            results_guide=payload.get("results_guide", str(Path(payload["out_dir"]) / "README.txt")),
            filter_budget=filter_budget,
        )
