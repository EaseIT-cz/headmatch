from __future__ import annotations

import json
import os
from dataclasses import fields
from pathlib import Path
from typing import Any

from .contracts import CONFIG_SCHEMA_VERSION, FrontendConfig

CONFIG_FILENAME = "config.json"


def default_config_dir() -> Path:
    from .paths import config_dir
    return config_dir()


def default_config_path() -> Path:
    return default_config_dir() / CONFIG_FILENAME


# Map new platform-neutral field names to the canonical dataclass fields
_FIELD_ALIASES = {
    "output_target": "pipewire_output_target",
    "input_target": "pipewire_input_target",
}


def _coerce_payload(payload: dict[str, Any]) -> FrontendConfig:
    allowed = {field.name for field in fields(FrontendConfig)}
    filtered = {}
    for key, value in payload.items():
        # Accept new field names, mapping to canonical names
        canonical = _FIELD_ALIASES.get(key, key)
        if canonical in allowed:
            # New-style names don't overwrite existing old-style values
            if canonical not in filtered:
                filtered[canonical] = value
    if "schema_version" not in filtered:
        filtered["schema_version"] = CONFIG_SCHEMA_VERSION
    return FrontendConfig(**filtered)


def load_config(path: str | Path | None = None) -> FrontendConfig:
    config_path = Path(path).expanduser() if path is not None else default_config_path()
    if not config_path.exists():
        return FrontendConfig()
    try:
        payload = json.loads(config_path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in config file {config_path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Config file must contain a JSON object: {config_path}")
    return _coerce_payload(payload)


def save_config(config: FrontendConfig, path: str | Path | None = None) -> Path:
    config_path = Path(path).expanduser() if path is not None else default_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config.to_dict(), indent=2) + "\n", encoding="utf-8")
    return config_path


def load_or_create_config(path: str | Path | None = None) -> tuple[FrontendConfig, Path, bool]:
    config_path = Path(path).expanduser() if path is not None else default_config_path()
    created = False
    if config_path.exists():
        return load_config(config_path), config_path, created
    config = FrontendConfig()
    try:
        save_config(config, config_path)
        created = True
    except OSError:
        created = False
    return config, config_path, created


def update_config_from_args(args, *, existing: FrontendConfig | None = None) -> FrontendConfig:
    config = existing or FrontendConfig()
    config.default_output_dir = getattr(args, "out_dir", config.default_output_dir)
    config.preferred_target_csv = getattr(args, "target_csv", config.preferred_target_csv)
    config.pipewire_output_target = getattr(args, "output_target", config.pipewire_output_target)
    config.pipewire_input_target = getattr(args, "input_target", config.pipewire_input_target)
    config.sample_rate = getattr(args, "sample_rate", config.sample_rate)
    config.duration_s = getattr(args, "duration", config.duration_s)
    config.f_start_hz = getattr(args, "f_start", config.f_start_hz)
    config.f_end_hz = getattr(args, "f_end", config.f_end_hz)
    config.pre_silence_s = getattr(args, "pre_silence", config.pre_silence_s)
    config.post_silence_s = getattr(args, "post_silence", config.post_silence_s)
    config.amplitude = getattr(args, "amplitude", config.amplitude)
    config.max_filters = getattr(args, "max_filters", config.max_filters)
    iterations = getattr(args, "iterations", None)
    if getattr(args, "cmd", None) == "start" and iterations is not None:
        config.start_iterations = iterations
    elif getattr(args, "cmd", None) == "iterate" and iterations is not None:
        config.iterate_iterations = iterations
    return config
