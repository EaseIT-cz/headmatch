"""Platform-agnostic measurement orchestration.

Keeps the public API that cli.py, gui.py, pipeline.py, and tests import.
Audio I/O is delegated to the active AudioBackend (PipeWire on Linux,
PortAudio on macOS/Windows in a future release).
"""
from __future__ import annotations

import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from .app_identity import get_app_identity
from .audio_backend import (
    AudioDevice,
    DeviceConfig,
    DeviceSelection,
    MeasurementPaths,
    get_audio_backend,
)
from .contracts import FrontendConfig
from .io_utils import save_json, write_wav
from .signals import SweepSpec, generate_log_sweep


# ── Backward-compatible aliases ──
# Preserve the public API.  New code should prefer audio_backend types.

PipeWireTarget = AudioDevice

@dataclass(frozen=True)
class PipeWireTargetSelection:
    """Legacy wrapper around DeviceSelection."""
    playback_targets: tuple[AudioDevice, ...]
    capture_targets: tuple[AudioDevice, ...]
    selected_playback: str
    selected_capture: str

PipeWireDeviceConfig = DeviceConfig


# ── Platform-agnostic types ──

@dataclass(frozen=True)
class DoctorCheck:
    name: str
    ok: bool
    detail: str
    action: str | None = None


@dataclass
class OfflineMeasurementPlan:
    sweep_wav: Path
    metadata_json: Path
    notes: str = ""


# ── Helpers ──

def require_executable(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"Required executable not found: {name}")


def render_sweep_file(spec: SweepSpec, path: str | Path) -> Path:
    stereo, _ = generate_log_sweep(spec)
    write_wav(path, stereo, spec.sample_rate)
    return Path(path)


def prepare_offline_measurement(spec: SweepSpec, plan: OfflineMeasurementPlan) -> dict:
    plan.sweep_wav.parent.mkdir(parents=True, exist_ok=True)
    plan.metadata_json.parent.mkdir(parents=True, exist_ok=True)
    render_sweep_file(spec, plan.sweep_wav)
    identity = get_app_identity()
    payload = {
        "generated_by": identity.as_metadata(),
        "mode": "offline",
        "recommended_recorder": "Zoom H2n",
        "recommended_format": {
            "sample_rate": spec.sample_rate,
            "channels": 2,
            "bit_depth": "16 or 24-bit PCM",
        },
        "instructions": [
            "Connect the Roland CS-10EM mic plug to the recorder's external mic input with plug-in power enabled.",
            "Disable auto gain, limiter, low cut, and any other processing.",
            "Record the whole sweep plus a bit of extra tail; do not trim the file before analysis.",
            "If you are doing validation, create one recording per preset state and keep filenames explicit.",
        ],
        "notes": plan.notes,
        "sweep": asdict(spec),
        "files": {
            "sweep_wav": str(plan.sweep_wav),
        },
    }
    save_json(plan.metadata_json, payload)
    return payload


# ── Backend-delegated functions ──

def list_pipewire_targets() -> list[AudioDevice]:
    """Discover audio devices via the active backend."""
    backend = get_audio_backend()
    return backend.discover_devices()


def format_pipewire_targets(targets: list[AudioDevice]) -> str:
    """Format device list for CLI output."""
    backend = get_audio_backend()
    return backend.format_device_list(targets)


def get_pipewire_default_targets() -> dict[str, str]:
    """Get default playback/capture device IDs."""
    backend = get_audio_backend()
    return backend.get_default_devices()


def collect_pipewire_target_selection(config: FrontendConfig) -> PipeWireTargetSelection:
    """Resolve device selection using the active backend."""
    backend = get_audio_backend()
    sel = backend.resolve_device_selection(
        saved_output=config.pipewire_output_target,
        saved_input=config.pipewire_input_target,
    )
    return PipeWireTargetSelection(
        playback_targets=sel.playback_devices,
        capture_targets=sel.capture_devices,
        selected_playback=sel.selected_playback,
        selected_capture=sel.selected_capture,
    )


def run_pipewire_measurement(spec: SweepSpec, paths: MeasurementPaths, device: DeviceConfig) -> Path:
    """Run a play-and-record measurement via the active backend."""
    backend = get_audio_backend()
    return backend.play_and_record(spec, paths, device)


def _saved_target_matches_discovery(saved_target: str, kind: str, targets: list[AudioDevice]) -> bool:
    saved = saved_target.strip()
    if not saved:
        return False
    return any(d.kind == kind and saved in d.device_id for d in targets)


def collect_doctor_checks(config_path: Path, config: FrontendConfig) -> list[DoctorCheck]:
    checks = [
        DoctorCheck(
            name="config file",
            ok=config_path.exists(),
            detail=f"Using {config_path}",
            action="Run any HeadMatch command once to create the default config file." if not config_path.exists() else None,
        )
    ]

    backend = get_audio_backend()
    checks.extend(backend.collect_doctor_checks())

    # Check saved targets against discovered devices
    try:
        discovered = list_pipewire_targets()
    except RuntimeError:
        discovered = None

    if config.pipewire_output_target:
        if discovered is None:
            checks.append(DoctorCheck(name="saved output target", ok=True, detail=f"Configured: {config.pipewire_output_target}"))
        else:
            output_found = _saved_target_matches_discovery(config.pipewire_output_target, "playback", discovered)
            checks.append(DoctorCheck(
                name="saved output target",
                ok=output_found,
                detail=f"Configured and found: {config.pipewire_output_target}" if output_found else f"Configured but not found now: {config.pipewire_output_target}",
                action=None if output_found else "Run 'headmatch list-targets' and save an updated --output-target if the device name changed.",
            ))
    else:
        checks.append(DoctorCheck(
            name="saved output target",
            ok=False,
            detail="No default --output-target saved yet.",
            action="Run a measure/start command with --output-target once if auto-selection is unreliable.",
        ))

    if config.pipewire_input_target:
        if discovered is None:
            checks.append(DoctorCheck(name="saved input target", ok=True, detail=f"Configured: {config.pipewire_input_target}"))
        else:
            input_found = _saved_target_matches_discovery(config.pipewire_input_target, "capture", discovered)
            checks.append(DoctorCheck(
                name="saved input target",
                ok=input_found,
                detail=f"Configured and found: {config.pipewire_input_target}" if input_found else f"Configured but not found now: {config.pipewire_input_target}",
                action=None if input_found else "Run 'headmatch list-targets' and save an updated --input-target if the device name changed.",
            ))
    else:
        checks.append(DoctorCheck(
            name="saved input target",
            ok=False,
            detail="No default --input-target saved yet.",
            action="Run a measure/start command with --input-target once if auto-selection is unreliable.",
        ))

    checks.append(DoctorCheck(
        name="starter sweep settings",
        ok=config.sample_rate > 0 and config.duration_s > 0,
        detail=(
            f"{config.sample_rate} Hz, {config.duration_s:g} s, "
            f"{config.f_start_hz:g}-{config.f_end_hz:g} Hz sweep, amplitude {config.amplitude:g}"
        ),
        action="Reset the config file if these values look wrong for a beginner setup." if config.sample_rate <= 0 or config.duration_s <= 0 else None,
    ))

    return checks


def format_doctor_report(checks: list[DoctorCheck], *, config_path: Path) -> str:
    ok_count = sum(check.ok for check in checks)
    lines = [
        "HeadMatch doctor",
        "================",
        f"Config path: {config_path}",
        f"Readiness: {ok_count}/{len(checks)} checks look good.",
        "",
    ]

    actions: list[str] = []
    for check in checks:
        status = "OK" if check.ok else "WARN"
        lines.append(f"[{status}] {check.name}: {check.detail}")
        if check.action:
            actions.append(f"- {check.name}: {check.action}")

    if actions:
        lines.extend(["", "Suggested next steps:"])
        lines.extend(actions)
    else:
        lines.extend([
            "",
            "Suggested next step:",
            "- Try 'headmatch list-targets' to confirm the exact device names before your first measurement.",
        ])

    return "\n".join(lines)
