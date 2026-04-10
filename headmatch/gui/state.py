"""GUI state management.

This module contains state dataclasses and state loading utilities
for the HeadMatch GUI.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ..app_identity import get_app_identity
from ..contracts import FrontendConfig
from ..measure import collect_doctor_checks, format_doctor_report
from ..settings import load_or_create_config


@dataclass(frozen=True)
class GuiState:
    """Immutable snapshot of GUI configuration state."""
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


# Type aliases for dependency injection
ConfigLoader = Callable[[str | Path | None], tuple[FrontendConfig, Path, bool]]
OnlineRunner = Callable[..., list[dict]]
OfflinePrepareRunner = Callable[..., dict]
OfflineFitRunner = Callable[..., dict]
DoctorReportRunner = Callable[[Path, FrontendConfig], str]


# Legacy output directories to ignore when resolving defaults
_LEGACY_OUTPUT_DIRS = {"out/session_01", "out\\session_01"}


def _resolve_default_output_dir(saved: str | None) -> str:
    """Return a sensible default output dir, ignoring legacy defaults."""
    if saved and saved.strip() not in _LEGACY_OUTPUT_DIRS:
        return saved
    return str(Path.home() / "Documents" / "HeadMatch" / "session_01")


def build_doctor_report(config_path: Path, config: FrontendConfig) -> str:
    """Build a doctor report using the injected or default collect/format functions."""
    gui_mod = sys.modules.get('headmatch.gui')
    collect = getattr(gui_mod, 'collect_doctor_checks', collect_doctor_checks)
    format_report = getattr(gui_mod, 'format_doctor_report', format_doctor_report)
    return format_report(collect(config_path, config), config_path=config_path)


def load_gui_state(
    config_path: str | Path | None = None,
    *,
    config_loader: ConfigLoader = load_or_create_config,
) -> GuiState:
    """Load GUI state from configuration file.
    
    Args:
        config_path: Optional path to config file
        config_loader: Config loader function (for testing)
        
    Returns:
        GuiState instance with loaded configuration
    """
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
