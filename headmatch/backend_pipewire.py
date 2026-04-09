"""PipeWire audio backend for Linux.

Implements the AudioBackend protocol using pw-dump, pw-play, pw-record,
and wpctl for device discovery and measurement.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .audio_backend import AudioBackend, AudioDevice, DeviceConfig, DeviceSelection, MeasurementPaths
from .signals import SweepSpec


# ── Internal helpers (moved from measure.py) ──

def _run_discovery(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False)


def _classify_media_class(media_class: str) -> Optional[str]:
    if media_class.startswith('Audio/Sink'):
        return 'playback'
    if media_class.startswith('Audio/Source'):
        return 'capture'
    return None


def _parse_pw_dump(payload: list[dict]) -> list[AudioDevice]:
    devices: list[AudioDevice] = []
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
        kind = _classify_media_class(media_class)
        if kind is None:
            continue
        node_name = str(props.get('node.name') or '').strip()
        if not node_name:
            continue
        key = (kind, node_name)
        if key in seen:
            continue
        seen.add(key)
        description = str(props.get('node.description') or '').strip()
        nick = str(props.get('node.nick') or '').strip()
        label = description or nick or node_name
        devices.append(AudioDevice(
            kind=kind,
            device_id=node_name,
            label=label,
            description=description,
            raw_info={'node_name': node_name, 'nick': nick, 'media_class': media_class},
        ))
    devices.sort(key=lambda d: (d.kind, d.label.lower(), d.device_id.lower()))
    return devices


def _parse_wpctl_default_ids(status_text: str) -> dict[str, int]:
    default_ids: dict[str, int] = {}
    current_kind: str | None = None
    for raw_line in status_text.splitlines():
        stripped = raw_line.strip()
        if 'Sinks:' in stripped:
            current_kind = 'playback'
            continue
        if 'Sources:' in stripped:
            current_kind = 'capture'
            continue
        if stripped.endswith(':') and stripped not in {'Sinks:', 'Sources:'}:
            current_kind = None
            continue
        if current_kind is None or '*' not in stripped:
            continue
        match = re.search(r'\*\s*(\d+)\.', stripped)
        if match is None:
            continue
        default_ids[current_kind] = int(match.group(1))
    return default_ids


def _parse_wpctl_inspect_node_name(inspect_text: str) -> str | None:
    match = re.search(r'node\.name\s*=\s*"([^"]+)"', inspect_text)
    if match is None:
        return None
    node_name = match.group(1).strip()
    return node_name or None


def _resolve_preferred(kind: str, saved_target: str | None, devices: list[AudioDevice], default_id: str | None) -> str:
    matching = [d for d in devices if d.kind == kind]
    saved = (saved_target or '').strip()
    if saved:
        for d in matching:
            if saved in d.device_id:
                return d.device_id
    default_name = (default_id or '').strip()
    if default_name:
        for d in matching:
            if d.device_id == default_name:
                return d.device_id
    if matching:
        return matching[0].device_id
    return ''


def _require_target(value: Optional[str], label: str) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    if not value:
        raise ValueError(f'{label} cannot be empty')
    return value


# ── PipeWireBackend ──

class PipeWireBackend:
    """AudioBackend implementation using PipeWire CLI tools."""

    name = "pipewire"

    def discover_devices(self) -> list[AudioDevice]:
        if shutil.which('pw-dump') is None:
            raise RuntimeError('PipeWire discovery requires pw-dump. Install PipeWire tools and try again.')
        result = _run_discovery(['pw-dump'])
        if result.returncode != 0:
            message = (result.stderr or result.stdout or 'pw-dump failed').strip()
            raise RuntimeError(f'PipeWire discovery failed. {message}')
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError('PipeWire discovery returned invalid JSON from pw-dump.') from exc
        if not isinstance(payload, list):
            raise RuntimeError('PipeWire discovery returned an unexpected payload from pw-dump.')
        return _parse_pw_dump(payload)

    def get_default_devices(self) -> dict[str, str]:
        if shutil.which('wpctl') is None:
            return {}
        status_result = _run_discovery(['wpctl', 'status'])
        if status_result.returncode != 0:
            return {}
        default_ids = _parse_wpctl_default_ids(status_result.stdout)
        defaults: dict[str, str] = {}
        for kind, object_id in default_ids.items():
            inspect_result = _run_discovery(['wpctl', 'inspect', str(object_id)])
            if inspect_result.returncode != 0:
                continue
            node_name = _parse_wpctl_inspect_node_name(inspect_result.stdout)
            if node_name:
                defaults[kind] = node_name
        return defaults

    def resolve_device_selection(
        self,
        saved_output: Optional[str],
        saved_input: Optional[str],
    ) -> DeviceSelection:
        try:
            devices = self.discover_devices()
        except RuntimeError:
            devices = []
        defaults = self.get_default_devices()
        return DeviceSelection(
            playback_devices=tuple(d for d in devices if d.kind == 'playback'),
            capture_devices=tuple(d for d in devices if d.kind == 'capture'),
            selected_playback=_resolve_preferred('playback', saved_output, devices, defaults.get('playback')),
            selected_capture=_resolve_preferred('capture', saved_input, devices, defaults.get('capture')),
        )

    def play_and_record(
        self,
        spec: SweepSpec,
        paths: MeasurementPaths,
        device: DeviceConfig,
    ) -> Path:
        from .measure import render_sweep_file, require_executable

        require_executable("pw-play")
        require_executable("pw-record")
        device = DeviceConfig(
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

        stderr_path = paths.recording_wav.parent / 'pw-record-stderr.log'
        with open(stderr_path, 'w', encoding='utf-8') as stderr_file:
            rec_proc = subprocess.Popen(rec_cmd, stdout=subprocess.DEVNULL, stderr=stderr_file)
            try:
                time.sleep(max(0.35, spec.pre_silence_s * 0.75))
                play_result = subprocess.run(play_cmd, capture_output=True, text=True, check=False)
                if play_result.returncode != 0:
                    message = (play_result.stderr or play_result.stdout or 'pw-play failed').strip()
                    raise RuntimeError(
                        f"Playback failed. {message} Try 'headmatch list-targets' to confirm the right --output-target."
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
            if stderr_path.exists():
                stderr = stderr_path.read_text(encoding='utf-8').strip()
            raise RuntimeError(
                'Capture did not produce a usable WAV file. '
                "Confirm the playback/capture targets, run 'headmatch list-targets' if needed, and try again."
                + (f' {stderr}' if stderr else '')
            )
        return paths.recording_wav

    def format_device_list(self, devices: list[AudioDevice]) -> str:
        lines = [
            'Audio targets you can pass to --output-target / --input-target',
            '',
            'Use the device ID value after the arrow. Partial matches usually work, but the full name is safest.',
            '',
        ]
        grouped = {
            'playback': [d for d in devices if d.kind == 'playback'],
            'capture': [d for d in devices if d.kind == 'capture'],
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
                for d in entries:
                    mc = d.raw_info.get('media_class', '')
                    extra = f' [{mc}]' if d.label != d.device_id and mc else ''
                    lines.append(f'  - {d.label} -> {d.device_id}{extra}')
            lines.append('')
        lines.extend([
            'Example:',
            '  headmatch measure --out-dir out/session_01 --output-target alsa_output.usb-... --input-target alsa_input.usb-...',
            '',
            'Tip: if you are unsure, copy the exact device ID first, get one successful run, then shorten if you want.',
        ])
        return '\n'.join(lines)

    def collect_doctor_checks(self) -> list:
        from .measure import DoctorCheck

        checks = []
        for executable in ('pw-dump', 'pw-play', 'pw-record'):
            resolved = shutil.which(executable)
            checks.append(DoctorCheck(
                name=executable,
                ok=resolved is not None,
                detail=resolved or f'{executable} was not found on PATH',
                action='Install PipeWire user tools and make sure they are on PATH.' if resolved is None else None,
            ))

        if shutil.which('pw-dump') is None:
            checks.append(DoctorCheck(
                name='audio discovery',
                ok=False,
                detail='Skipped because pw-dump is not available.',
                action="Install pw-dump, then rerun 'headmatch doctor' or 'headmatch list-targets'.",
            ))
        else:
            try:
                devices = self.discover_devices()
                playback = sum(d.kind == 'playback' for d in devices)
                capture = sum(d.kind == 'capture' for d in devices)
                ok = playback > 0 and capture > 0
                detail = f'Found {playback} playback and {capture} capture target(s).'
                action = None if ok else "Make sure PipeWire is running and your audio devices are connected, then try 'headmatch list-targets'."
                checks.append(DoctorCheck(name='audio discovery', ok=ok, detail=detail, action=action))
            except RuntimeError as exc:
                checks.append(DoctorCheck(
                    name='audio discovery',
                    ok=False,
                    detail=str(exc),
                    action="Confirm PipeWire is running, then rerun 'headmatch list-targets'.",
                ))
        return checks
