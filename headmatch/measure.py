from __future__ import annotations

import json
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from .app_identity import get_app_identity
from .contracts import FrontendConfig
from .io_utils import save_json, write_wav
from .signals import SweepSpec, generate_log_sweep




@dataclass(frozen=True)
class PipeWireTarget:
    kind: str
    node_name: str
    description: str
    nick: str
    media_class: str

    @property
    def label(self) -> str:
        for value in (self.description, self.nick, self.node_name):
            if value:
                return value
        return self.node_name


def _run_pipewire_discovery(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False)


def _classify_pipewire_target(media_class: str) -> Optional[str]:
    if media_class.startswith('Audio/Sink'):
        return 'playback'
    if media_class.startswith('Audio/Source'):
        return 'capture'
    return None


def _parse_pipewire_targets(payload: list[dict]) -> list[PipeWireTarget]:
    targets: list[PipeWireTarget] = []
    seen: set[tuple[str, str]] = set()
    for item in payload:
        if not isinstance(item, dict):
            continue
        info = item.get('info')
        if not isinstance(info, dict):
            continue
        props = info.get('props')
        if not isinstance(props, dict):
            continue
        media_class = str(props.get('media.class') or '')
        kind = _classify_pipewire_target(media_class)
        if kind is None:
            continue
        node_name = str(props.get('node.name') or '').strip()
        if not node_name:
            continue
        key = (kind, node_name)
        if key in seen:
            continue
        seen.add(key)
        targets.append(
            PipeWireTarget(
                kind=kind,
                node_name=node_name,
                description=str(props.get('node.description') or '').strip(),
                nick=str(props.get('node.nick') or '').strip(),
                media_class=media_class,
            )
        )
    targets.sort(key=lambda target: (target.kind, target.label.lower(), target.node_name.lower()))
    return targets


def list_pipewire_targets() -> list[PipeWireTarget]:
    if shutil.which('pw-dump') is None:
        raise RuntimeError('PipeWire discovery requires pw-dump. Install PipeWire tools and try again.')
    result = _run_pipewire_discovery(['pw-dump'])
    if result.returncode != 0:
        message = (result.stderr or result.stdout or 'pw-dump failed').strip()
        raise RuntimeError(f'PipeWire discovery failed. {message}')
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError('PipeWire discovery returned invalid JSON from pw-dump.') from exc
    if not isinstance(payload, list):
        raise RuntimeError('PipeWire discovery returned an unexpected payload from pw-dump.')
    return _parse_pipewire_targets(payload)


def format_pipewire_targets(targets: list[PipeWireTarget]) -> str:
    lines = [
        'PipeWire targets you can pass to --output-target / --input-target',
        '',
        'Use the node.name value after the arrow. Partial matches usually work, but the full node name is safest.',
        'Pick one playback target for the headphone or speaker output you want to test, and one capture target for the mic or recorder input that hears it.',
        'Avoid monitor/loopback-style entries unless you intentionally want to record the computer output instead of the acoustic result.',
        '',
    ]
    grouped = {
        'playback': [target for target in targets if target.kind == 'playback'],
        'capture': [target for target in targets if target.kind == 'capture'],
    }
    for kind, title in (('playback', 'Playback targets (--output-target)'), ('capture', 'Capture targets (--input-target)')):
        lines.append(title)
        if kind == 'playback':
            lines.append('  Choose the DAC, headphones, speakers, or interface output you expect the sweep to play through.')
        else:
            lines.append('  Choose the mic, recorder, or interface input connected to your measurement rig.')
        entries = grouped[kind]
        if not entries:
            lines.append('  (none found)')
        else:
            for target in entries:
                extra = '' if target.label == target.node_name else f' [{target.media_class}]'
                lines.append(f'  - {target.label} -> {target.node_name}{extra}')
        lines.append('')
    lines.extend([
        'Example:',
        '  headmatch measure --out-dir out/session_01 --output-target alsa_output.usb-... --input-target alsa_input.usb-...',
        '',
        'Tip: if you are unsure, copy the exact node.name values first, get one successful run, then shorten them later if you want.',
    ])
    return '\n'.join(lines)


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    ok: bool
    detail: str
    action: str | None = None


def collect_doctor_checks(config_path: Path, config: FrontendConfig) -> list[DoctorCheck]:
    checks = [
        DoctorCheck(
            name='config file',
            ok=config_path.exists(),
            detail=f'Using {config_path}',
            action='Run any HeadMatch command once to create the default config file.' if not config_path.exists() else None,
        )
    ]

    for executable in ('pw-dump', 'pw-play', 'pw-record'):
        resolved = shutil.which(executable)
        checks.append(
            DoctorCheck(
                name=executable,
                ok=resolved is not None,
                detail=resolved or f'{executable} was not found on PATH',
                action='Install PipeWire user tools and make sure they are on PATH.' if resolved is None else None,
            )
        )

    if shutil.which('pw-dump') is None:
        checks.append(
            DoctorCheck(
                name='PipeWire discovery',
                ok=False,
                detail='Skipped because pw-dump is not available.',
                action="Install pw-dump, then rerun 'headmatch doctor' or 'headmatch list-targets'.",
            )
        )
    else:
        try:
            targets = list_pipewire_targets()
            playback = sum(target.kind == 'playback' for target in targets)
            capture = sum(target.kind == 'capture' for target in targets)
            ok = playback > 0 and capture > 0
            detail = f'Found {playback} playback and {capture} capture target(s).'
            action = None if ok else "Make sure PipeWire is running and your audio devices are connected, then try 'headmatch list-targets'."
            checks.append(DoctorCheck(name='PipeWire discovery', ok=ok, detail=detail, action=action))
        except RuntimeError as exc:
            checks.append(
                DoctorCheck(
                    name='PipeWire discovery',
                    ok=False,
                    detail=str(exc),
                    action="Confirm PipeWire is running, then rerun 'headmatch list-targets'.",
                )
            )

    if config.pipewire_output_target:
        checks.append(DoctorCheck(name='saved output target', ok=True, detail=f"Configured: {config.pipewire_output_target}"))
    else:
        checks.append(
            DoctorCheck(
                name='saved output target',
                ok=False,
                detail='No default --output-target saved yet.',
                action="Run a measure/start command with --output-target once if auto-selection is unreliable.",
            )
        )

    if config.pipewire_input_target:
        checks.append(DoctorCheck(name='saved input target', ok=True, detail=f"Configured: {config.pipewire_input_target}"))
    else:
        checks.append(
            DoctorCheck(
                name='saved input target',
                ok=False,
                detail='No default --input-target saved yet.',
                action="Run a measure/start command with --input-target once if auto-selection is unreliable.",
            )
        )

    checks.append(
        DoctorCheck(
            name='starter sweep settings',
            ok=config.sample_rate > 0 and config.duration_s > 0,
            detail=(
                f'{config.sample_rate} Hz, {config.duration_s:g} s, '
                f'{config.f_start_hz:g}-{config.f_end_hz:g} Hz sweep, amplitude {config.amplitude:g}'
            ),
            action='Reset the config file if these values look wrong for a beginner setup.' if config.sample_rate <= 0 or config.duration_s <= 0 else None,
        )
    )

    return checks


def format_doctor_report(checks: list[DoctorCheck], *, config_path: Path) -> str:
    ok_count = sum(check.ok for check in checks)
    lines = [
        'HeadMatch doctor',
        '================',
        f'Config path: {config_path}',
        f'Readiness: {ok_count}/{len(checks)} checks look good.',
        '',
    ]

    actions: list[str] = []
    for check in checks:
        status = 'OK' if check.ok else 'WARN'
        lines.append(f'[{status}] {check.name}: {check.detail}')
        if check.action:
            actions.append(f'- {check.name}: {check.action}')

    if actions:
        lines.extend(['', 'Suggested next steps:'])
        lines.extend(actions)
    else:
        lines.extend([
            '',
            'Suggested next step:',
            "- Try 'headmatch list-targets' to confirm the exact PipeWire node names before your first measurement.",
        ])

    return '\n'.join(lines)


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
            raise RuntimeError(
                f"PipeWire playback failed. {message} Try 'headmatch list-targets' to confirm the right --output-target."
            )
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
            "Confirm the playback/capture targets, run 'headmatch list-targets' if needed, and try again."
            + (f' {stderr}' if stderr else '')
        )
    return paths.recording_wav
