from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ..app_identity import get_app_identity
from ..contracts import FrontendConfig
from ..measure import collect_doctor_checks, format_doctor_report
from ..settings import load_or_create_config


__all__ = [
    'NavigationItem',
    'GuiState',
    'ConfigLoader',
    'OnlineRunner',
    'OfflinePrepareRunner',
    'OfflineFitRunner',
    'DoctorReportRunner',
    'BASIC_NAV_ITEMS',
    'NAV_ITEMS',
    'load_gui_state',
    'build_doctor_report',
]


@dataclass(frozen=True)
class NavigationItem:
    key: str
    label: str


@dataclass(frozen=True)
class GuiState:
    version_display: str
    config_path: Path
    config_created: bool
    current_view: str
    mode: str
    default_output_dir: str
    preferred_target_csv: str
    pipewire_output_target: str
    pipewire_input_target: str
    start_iterations: int
    max_filters: int
    sample_rate: int
    duration_s: float
    f_start_hz: float
    f_end_hz: float
    pre_silence_s: float
    post_silence_s: float
    amplitude: float


ConfigLoader = Callable[[str | Path | None], tuple[FrontendConfig, Path, bool]]
OnlineRunner = Callable[..., list[dict]]
OfflinePrepareRunner = Callable[[object, object], dict]  # SweepSpec, OfflineMeasurementPlan
OfflineFitRunner = Callable[..., dict]
DoctorReportRunner = Callable[[Path, FrontendConfig], str]


BASIC_NAV_ITEMS: tuple[NavigationItem, ...] = (
    NavigationItem("basic-mode", "Basic Workflow"),
    NavigationItem("hearing-test", "Hearing Test"),
    NavigationItem("basic-clone-target", "Clone Target"),
    NavigationItem("history", "Results"),
)

NAV_ITEMS: tuple[NavigationItem, ...] = (
    NavigationItem("measure-online", "Measure"),
    NavigationItem("hearing-test", "Hearing Test"),
    NavigationItem("setup-check", "Setup Check"),
    NavigationItem("prepare-offline", "Prepare Offline"),
    NavigationItem("target-editor", "Target Editor"),
    NavigationItem("import-apo", "Import APO"),
    NavigationItem("fetch-curve", "Fetch Curve"),
    NavigationItem("history", "Results"),
)


_LEGACY_OUTPUT_DIRS = {"out/session_01", "out\\session_01"}


def _resolve_default_output_dir(saved: str | None) -> str:
    """Return a sensible default output dir, ignoring legacy defaults."""
    if saved and saved.strip() not in _LEGACY_OUTPUT_DIRS:
        return saved
    return str(Path.home() / "Documents" / "HeadMatch" / "session_01")


def load_gui_state(
    config_path: str | Path | None = None,
    *,
    config_loader: ConfigLoader = load_or_create_config,
) -> GuiState:
    identity = get_app_identity()
    config, resolved_path, created = config_loader(config_path)
    return GuiState(
        version_display=identity.version_display,
        config_path=Path(resolved_path),
        config_created=created,
        current_view="basic-mode" if config.mode == "basic" else "measure-online",
        mode=config.mode,
        default_output_dir=_resolve_default_output_dir(config.default_output_dir),
        preferred_target_csv=config.preferred_target_csv or "",
        pipewire_output_target=config.pipewire_output_target or "",
        pipewire_input_target=config.pipewire_input_target or "",
        start_iterations=config.start_iterations,
        max_filters=config.max_filters,
        sample_rate=config.sample_rate,
        duration_s=config.duration_s,
        f_start_hz=config.f_start_hz,
        f_end_hz=config.f_end_hz,
        pre_silence_s=config.pre_silence_s,
        post_silence_s=config.post_silence_s,
        amplitude=config.amplitude,
    )


def build_doctor_report(config_path: Path, config: FrontendConfig) -> str:
    import headmatch.gui as gui_mod
    _collect = getattr(gui_mod, 'collect_doctor_checks', collect_doctor_checks)
    _format = getattr(gui_mod, 'format_doctor_report', format_doctor_report)
    checks = _collect(config_path, config)
    return _format(checks, config_path=config_path)