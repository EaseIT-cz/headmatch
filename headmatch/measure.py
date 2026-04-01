from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from .app_identity import get_app_identity
from .io_utils import save_json, write_wav
from .signals import SweepSpec, generate_log_sweep


@dataclass
class PipeWireDeviceConfig:
    output_target: Optional[str] = None
    input_target: Optional[str] = None


@dataclass
class MeasurementPaths:
    sweep_wav: Path
    recording_wav: Path


@dataclass
class OfflineMeasurementPlan:
    sweep_wav: Path
    metadata_json: Path
    notes: str = ""



def _require_target(value: Optional[str], label: str) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    if not value:
        raise ValueError(f'{label} cannot be empty')
    return value


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
        'generated_by': identity.as_metadata(),
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



def run_pipewire_measurement(spec: SweepSpec, paths: MeasurementPaths, device: PipeWireDeviceConfig) -> Path:
    require_executable("pw-play")
    require_executable("pw-record")
    device = PipeWireDeviceConfig(
        output_target=_require_target(device.output_target, 'output_target'),
        input_target=_require_target(device.input_target, 'input_target'),
    )
    paths.sweep_wav.parent.mkdir(parents=True, exist_ok=True)
    paths.recording_wav.parent.mkdir(parents=True, exist_ok=True)
    render_sweep_file(spec, paths.sweep_wav)

    capture_guard_s = 1.0
    rec_cmd = ["pw-record", "--rate", str(spec.sample_rate), "--channels", "2", str(paths.recording_wav)]
    play_cmd = ["pw-play", "--rate", str(spec.sample_rate), "--channels", "2", str(paths.sweep_wav)]
    if device.input_target:
        rec_cmd.extend(["--target", device.input_target])
    if device.output_target:
        play_cmd.extend(["--target", device.output_target])

    rec_proc = subprocess.Popen(rec_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        time.sleep(max(0.35, spec.pre_silence_s * 0.75))
        play_result = subprocess.run(play_cmd, capture_output=True, text=True, check=False)
        if play_result.returncode != 0:
            message = (play_result.stderr or play_result.stdout or 'pw-play failed').strip()
            raise RuntimeError(f'PipeWire playback failed. {message}')
        time.sleep(capture_guard_s)
    except Exception:
        rec_proc.terminate()
        raise
    finally:
        time.sleep(0.25)
        rec_proc.terminate()
        try:
            rec_proc.wait(timeout=max(3.0, capture_guard_s + spec.post_silence_s + 1.0))
        except subprocess.TimeoutExpired:
            rec_proc.kill()
            rec_proc.wait(timeout=2)

    if not paths.recording_wav.exists() or paths.recording_wav.stat().st_size == 0:
        stderr = ''
        if rec_proc.stderr is not None:
            stderr = rec_proc.stderr.read().strip()
        raise RuntimeError(
            'PipeWire capture did not produce a usable WAV file. '
            'Confirm the playback/capture targets and try again.'
            + (f' {stderr}' if stderr else '')
        )
    return paths.recording_wav
