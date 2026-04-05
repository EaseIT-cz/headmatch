from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, TextIO

from .contracts import FrontendConfig, FrontendRunSummary
from .history import load_recent_runs, read_results_guide
from .measure import OfflineMeasurementPlan, prepare_offline_measurement
from .pipeline import iterative_measure_and_fit
from .signals import SweepSpec
from .settings import load_or_create_config, save_config

ConfigLoader = Callable[[str | Path | None], tuple[FrontendConfig, Path, bool]]


@dataclass(frozen=True)
class WizardState:
    mode: str
    out_dir: str
    output_target: str | None
    input_target: str | None
    target_csv: str | None
    max_filters: int
    iterations: int
    notes: str = ""


@dataclass(frozen=True)
class WizardResult:
    workflow: str
    mode: str
    out_dir: str
    next_steps: tuple[str, ...]
    details: str = ""


class WizardIO:
    def __init__(self, stdin: TextIO, stdout: TextIO):
        self.stdin = stdin
        self.stdout = stdout

    def write(self, text: str = "") -> None:
        self.stdout.write(text)
        if not text.endswith("\n"):
            self.stdout.write("\n")

    def prompt(self, label: str, default: str | None = None) -> str:
        suffix = f" [{default}]" if default not in {None, ""} else ""
        self.stdout.write(f"{label}{suffix}: ")
        self.stdout.flush()
        raw = self.stdin.readline()
        if raw == "":
            return default or ""
        value = raw.strip()
        if not value and default is not None:
            return default
        return value

    def choose(self, label: str, options: dict[str, str], default: str) -> str:
        self.write(label)
        for key, description in options.items():
            marker = " (default)" if key == default else ""
            self.write(f"  {key}) {description}{marker}")
        while True:
            choice = self.prompt("Choose", default=default).lower().strip()
            if choice in options:
                return choice
            self.write(f"Please enter one of: {', '.join(options)}")


def default_config_loader(config_path: str | Path | None = None) -> tuple[FrontendConfig, Path, bool]:
    return load_or_create_config(config_path)


class HeadMatchWizard:
    def __init__(self, io: WizardIO, config_loader: ConfigLoader = default_config_loader, config_path: str | Path | None = None):
        self.io = io
        self.config_loader = config_loader
        self.config_path = config_path

    def run(self) -> WizardResult:
        config, resolved_path, created = self.config_loader(self.config_path)
        self._print_header(config, resolved_path=resolved_path, created=created)
        mode = self.io.choose(
            "How do you want to start?",
            {
                "1": "Online guided run: play the sweep now and build EQ.",
                "2": "Offline prep: export sweep + plan so you can record first.",
                "3": "Browse recent runs and open the plain-language guide.",
            },
            default="1",
        )
        if mode == "3":
            return self._browse_history(config)
        state = self._collect_state(config, mode)
        result = self._run_online(state, config) if mode == "1" else self._run_offline(state, config)
        self._persist_config(config, resolved_path, state)
        return result

    def _print_header(self, config: FrontendConfig, *, resolved_path: Path, created: bool) -> None:
        self.io.write("headmatch TUI wizard")
        self.io.write("====================")
        self.io.write("This wizard keeps the first run simple and reuses the existing measurement pipeline.")
        if config.pipewire_output_target or config.pipewire_input_target:
            self.io.write("Saved device targets were found and preloaded below.")
        else:
            self.io.write("No saved device targets were found. Press Enter to accept safe defaults.")
            self.io.write("If setup feels uncertain, run 'headmatch doctor'. If names are unclear, run 'headmatch list-targets'.")
        self.io.write(f"Config path: {resolved_path}")
        if created:
            self.io.write("Created a default config file with safe starter values.")
        self.io.write()

    def _collect_state(self, config: FrontendConfig, mode: str) -> WizardState:
        out_dir = self.io.prompt("Output folder", default=config.default_output_dir or "out/session_01")
        output_target = self._optional_prompt("Playback target match", config.pipewire_output_target)
        input_target = self._optional_prompt("Capture target match", config.pipewire_input_target)
        target_csv = self._optional_prompt("Target CSV (optional)", config.preferred_target_csv)
        max_filters = self._int_prompt("Max PEQ filters per channel", default=config.max_filters)
        iterations_default = config.start_iterations if mode == "1" else 1
        iterations = self._int_prompt("Iterations", default=iterations_default)
        notes = ""
        if mode == "2":
            notes = self.io.prompt("Notes for the offline plan", default="")
        return WizardState(
            mode="online" if mode == "1" else "offline",
            out_dir=out_dir,
            output_target=output_target,
            input_target=input_target,
            target_csv=target_csv,
            max_filters=max_filters,
            iterations=iterations,
            notes=notes,
        )


    def _history_root_default(self, config: FrontendConfig) -> str:
        if config.default_output_dir:
            return str(Path(config.default_output_dir).expanduser().parent)
        return "out"

    def _browse_history(self, config: FrontendConfig) -> WizardResult:
        self.io.write()
        root = self.io.prompt("Search folder for recent runs", default=self._history_root_default(config))
        runs = load_recent_runs(root)
        if not runs:
            message = f"No run_summary.json files were found under {root}."
            self.io.write(message)
            self.io.write("Run 'headmatch start' or finish one offline fit first, then reopen the browser.")
            return WizardResult(workflow="history", mode="online", out_dir=root, next_steps=(message,), details=message)

        self.io.write("Recent runs")
        self.io.write("-----------")
        for index, entry in enumerate(runs, start=1):
            summary = entry.summary
            self.io.write(
                f"{index}) {summary.kind} | {summary.out_dir} | target={summary.target} | "
                f"filters L/R={summary.filters.left}/{summary.filters.right}"
            )

        while True:
            choice = self.io.prompt("Open run number", default="1")
            try:
                selected = runs[int(choice) - 1]
                break
            except (ValueError, IndexError):
                self.io.write(f"Please enter a number from 1 to {len(runs)}.")

        summary = selected.summary
        self.io.write()
        self.io.write("Run summary")
        self.io.write("-----------")
        self.io.write(f"folder: {summary.out_dir}")
        self.io.write(f"kind: {summary.kind}")
        self.io.write(f"sample rate: {summary.sample_rate} Hz")
        self.io.write(f"target: {summary.target}")
        self.io.write(
            "predicted error dB: "
            f"L rms {summary.predicted_error_db.left_rms}, "
            f"R rms {summary.predicted_error_db.right_rms}, "
            f"L max {summary.predicted_error_db.left_max}, "
            f"R max {summary.predicted_error_db.right_max}"
        )
        self.io.write()
        self.io.write(read_results_guide(selected.guide_path).rstrip())
        next_steps = (
            f"Review outputs in {summary.out_dir}.",
            f"Guide: {selected.guide_path}",
            f"Summary: {selected.summary_path}",
        )
        return WizardResult(workflow="history", mode="online", out_dir=summary.out_dir, next_steps=next_steps, details=str(selected.guide_path))

    def _persist_config(self, config: FrontendConfig, config_path: Path, state: WizardState) -> None:
        config.default_output_dir = state.out_dir
        config.pipewire_output_target = state.output_target
        config.pipewire_input_target = state.input_target
        config.preferred_target_csv = state.target_csv
        config.max_filters = state.max_filters
        if state.mode == "online":
            config.start_iterations = state.iterations
        try:
            save_config(config, config_path)
        except OSError:
            self.io.write("Note: could not save updated defaults to the config file.")

    def _optional_prompt(self, label: str, default: str | None) -> str | None:
        value = self.io.prompt(label, default=default or "")
        return value or None

    def _int_prompt(self, label: str, default: int) -> int:
        while True:
            value = self.io.prompt(label, default=str(default))
            try:
                parsed = int(value)
            except ValueError:
                self.io.write("Please enter a whole number.")
                continue
            if parsed <= 0:
                self.io.write("Please enter a value greater than 0.")
                continue
            return parsed

    def _build_sweep(self, config: FrontendConfig) -> SweepSpec:
        return SweepSpec(
            sample_rate=config.sample_rate,
            duration_s=config.duration_s,
            f_start=config.f_start_hz,
            f_end=config.f_end_hz,
            pre_silence_s=config.pre_silence_s,
            post_silence_s=config.post_silence_s,
            amplitude=config.amplitude,
        )

    def _run_online(self, state: WizardState, config: FrontendConfig) -> WizardResult:
        sweep = self._build_sweep(config)
        self.io.write()
        self.io.write("Step 1/3: building the guided online run...")
        self.io.write(f"  output folder: {state.out_dir}")
        self.io.write("Step 2/3: running measure -> analyze -> fit...")
        iterative_measure_and_fit(
            output_dir=state.out_dir,
            sweep_spec=sweep,
            target_path=state.target_csv,
            output_target=state.output_target,
            input_target=state.input_target,
            iterations=state.iterations,
            max_filters=state.max_filters,
        )
        self.io.write("Step 3/3: done.")
        self.io.write()
        next_steps = (
            f"Review outputs in {state.out_dir}.",
            "Start with run_summary.json, then use equalizer_apo.txt or camilladsp_full.yaml.",
            "If the wrong devices were used, rerun the wizard with playback/capture target matches.",
        )
        for step in next_steps:
            self.io.write(f"- {step}")
        return WizardResult(workflow="start", mode=state.mode, out_dir=state.out_dir, next_steps=next_steps)

    def _run_offline(self, state: WizardState, config: FrontendConfig) -> WizardResult:
        sweep = self._build_sweep(config)
        out_dir = Path(state.out_dir)
        self.io.write()
        self.io.write("Step 1/2: writing the offline sweep package...")
        prepare_offline_measurement(
            sweep,
            OfflineMeasurementPlan(
                sweep_wav=out_dir / "sweep.wav",
                metadata_json=out_dir / "measurement_plan.json",
                notes=state.notes,
            ),
        )
        self.io.write("Step 2/2: done.")
        self.io.write()
        next_steps = (
            f"Record the sweep from {out_dir / 'sweep.wav'} and save the capture as recording.wav.",
            f"Then run: headmatch fit --recording {out_dir / 'recording.wav'} --out-dir {out_dir / 'fit'}",
        )
        for step in next_steps:
            self.io.write(f"- {step}")
        return WizardResult(workflow="prepare-offline", mode=state.mode, out_dir=state.out_dir, next_steps=next_steps)


def run_tui(
    stdin: TextIO,
    stdout: TextIO,
    *,
    config_path: str | Path | None = None,
    config_loader: ConfigLoader = default_config_loader,
) -> WizardResult:
    wizard = HeadMatchWizard(WizardIO(stdin=stdin, stdout=stdout), config_loader=config_loader, config_path=config_path)
    return wizard.run()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="headmatch-tui", description="Launch the HeadMatch terminal wizard.")
    parser.add_argument(
        "--config",
        default=None,
        help="Optional path to a JSON config file. Default: ~/.config/headmatch/config.json or $XDG_CONFIG_HOME/headmatch/config.json.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    import sys

    parser = build_arg_parser()
    args = parser.parse_args(argv)
    run_tui(stdin=sys.stdin, stdout=sys.stdout, config_path=args.config)
