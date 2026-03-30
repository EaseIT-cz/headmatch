from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

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
    payload = {
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
    paths.sweep_wav.parent.mkdir(parents=True, exist_ok=True)
    paths.recording_wav.parent.mkdir(parents=True, exist_ok=True)
    render_sweep_file(spec, paths.sweep_wav)

    total_seconds = spec.pre_silence_s + spec.duration_s + spec.post_silence_s + 0.75
    rec_cmd = ["pw-record", "--rate", str(spec.sample_rate), "--channels", "2", str(paths.recording_wav)]
    play_cmd = ["pw-play", "--rate", str(spec.sample_rate), "--channels", "2", str(paths.sweep_wav)]
    if device.input_target:
        rec_cmd.extend(["--target", device.input_target])
    if device.output_target:
        play_cmd.extend(["--target", device.output_target])

    rec_proc = subprocess.Popen(rec_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        time.sleep(0.35)
        subprocess.run(play_cmd, capture_output=True, text=True, check=True)
        time.sleep(total_seconds - (spec.duration_s + spec.pre_silence_s + spec.post_silence_s))
    except Exception:
        rec_proc.terminate()
        raise
    finally:
        time.sleep(0.25)
        rec_proc.terminate()
        try:
            rec_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            rec_proc.kill()
    return paths.recording_wav
