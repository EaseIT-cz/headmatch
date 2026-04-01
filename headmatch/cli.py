from __future__ import annotations

import argparse
from pathlib import Path

from .app_identity import get_app_identity
from .settings import load_or_create_config, save_config, update_config_from_args


DEFAULT_START_ITERATIONS = 1


def parse_seconds(value: str) -> float:
    text = value.strip().lower()
    if text.endswith("s"):
        text = text[:-1]
    try:
        seconds = float(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid duration value: {value!r}") from exc
    if seconds <= 0:
        raise argparse.ArgumentTypeError("duration must be greater than 0")
    return seconds


def add_common_sweep_args(p: argparse.ArgumentParser, config) -> None:
    p.add_argument("--sample-rate", type=int, default=config.sample_rate)
    p.add_argument("--duration", type=parse_seconds, default=config.duration_s)
    p.add_argument("--f-start", type=float, default=config.f_start_hz)
    p.add_argument("--f-end", type=float, default=config.f_end_hz)
    p.add_argument("--pre-silence", type=parse_seconds, default=config.pre_silence_s)
    p.add_argument("--post-silence", type=parse_seconds, default=config.post_silence_s)
    p.add_argument("--amplitude", type=float, default=config.amplitude)


def spec_from_args(args):
    from .signals import SweepSpec

    return SweepSpec(
        sample_rate=args.sample_rate,
        duration_s=args.duration,
        f_start=args.f_start,
        f_end=args.f_end,
        pre_silence_s=args.pre_silence,
        post_silence_s=args.post_silence,
        amplitude=args.amplitude,
    )


def build_parser(config) -> argparse.ArgumentParser:
    identity = get_app_identity()
    parser = argparse.ArgumentParser(
        prog="headmatch",
        description="Beginner-first headphone measurement and EQ fitting.",
        epilog=(
            "Beginner path: run 'headmatch start --out-dir out/session_01' for a guided "
            "measure-and-fit pass, or 'headmatch prepare-offline --out-dir out/session_01' "
            "if you want to record first and import later."
        ),
    )
    parser.add_argument('--version', action='version', version=f'%(prog)s {identity.version_display}')
    parser.add_argument('--config', default=None, help='Optional path to a JSON config file. Default: ~/.config/headmatch/config.json or $XDG_CONFIG_HOME/headmatch/config.json.')
    sub = parser.add_subparsers(dest="cmd")

    p = sub.add_parser(
        "start",
        help="Beginner-first: measure once and build an EQ preset.",
        description=(
            "Run one guided online measurement pass and export CamillaDSP EQ files. "
            "This is the easiest place to start."
        ),
    )
    add_common_sweep_args(p, config)
    p.add_argument("--out-dir", required=True, help="Folder for the sweep, recording, reports, and YAML exports.")
    p.add_argument("--target-csv", default=config.preferred_target_csv, help="Optional target curve CSV. If omitted, fit toward flat.")
    p.add_argument("--output-target", default=config.pipewire_output_target, help="Optional PipeWire playback node match string.")
    p.add_argument("--input-target", default=config.pipewire_input_target, help="Optional PipeWire capture node match string.")
    p.add_argument("--max-filters", type=int, default=config.max_filters, help="Maximum PEQ filters per channel.")
    p.add_argument(
        "--iterations",
        type=int,
        default=config.start_iterations,
        help="Number of online measure-and-fit passes. Default: 1 for a simple first run.",
    )

    p = sub.add_parser("render-sweep", help="Generate a sweep WAV file.")
    add_common_sweep_args(p, config)
    p.add_argument("--out", required=True)

    p = sub.add_parser("measure", help="Play sweep via PipeWire and record the transfer.")
    add_common_sweep_args(p, config)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--output-target", default=config.pipewire_output_target)
    p.add_argument("--input-target", default=config.pipewire_input_target)

    p = sub.add_parser("prepare-offline", help="Create sweep + metadata for Zoom/H2n or SD-card recording workflows.")
    add_common_sweep_args(p, config)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--notes", default="")

    p = sub.add_parser("analyze", help="Analyze a recording WAV and write FR CSVs.")
    add_common_sweep_args(p, config)
    p.add_argument("--recording", required=True)
    p.add_argument("--out-dir", required=True)

    p = sub.add_parser("fit", help="Analyze a recording and build CamillaDSP EQ.")
    add_common_sweep_args(p, config)
    p.add_argument("--recording", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--target-csv", default=config.preferred_target_csv)
    p.add_argument("--max-filters", type=int, default=config.max_filters)

    p = sub.add_parser("fit-offline", help="Analyze an imported offline recording and build CamillaDSP EQ.")
    add_common_sweep_args(p, config)
    p.add_argument("--recording", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--target-csv", default=config.preferred_target_csv)
    p.add_argument("--max-filters", type=int, default=config.max_filters)

    p = sub.add_parser("clone-target", help="Create a clone target curve from source and target FR CSVs.")
    p.add_argument("--source-csv", required=True)
    p.add_argument("--target-csv", required=True)
    p.add_argument(
        "--out",
        required=True,
        help="Write the clone target to a new CSV file. Do not point this at your source or target input file.",
    )

    p = sub.add_parser("iterate", help="Measure -> fit -> export, repeated.")
    add_common_sweep_args(p, config)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--target-csv", default=config.preferred_target_csv)
    p.add_argument("--output-target", default=config.pipewire_output_target)
    p.add_argument("--input-target", default=config.pipewire_input_target)
    p.add_argument("--iterations", type=int, default=config.iterate_iterations)
    p.add_argument("--max-filters", type=int, default=config.max_filters)

    sub.add_parser(
        "tui",
        help="Launch the interactive beginner wizard.",
        description="Run a simple terminal wizard for online or offline measurement workflows.",
    )
    return parser


def print_beginner_guide(parser: argparse.ArgumentParser) -> None:
    identity = get_app_identity()
    print(f"headmatch beginner path ({identity.version_display})")
    print("================================")
    print("1) First try: headmatch start --out-dir out/session_01")
    print("   This runs one online measurement pass and exports CamillaDSP EQ files.")
    print()
    print("2) If your recorder is more reliable offline:")
    print("   headmatch prepare-offline --out-dir out/session_01")
    print("   ...record the sweep, then run:")
    print("   headmatch fit-offline --recording out/session_01/recording.wav --out-dir out/session_01/fit")
    print()
    print("Developer commands are still available below.")
    print()
    parser.print_help()


def print_next_steps(cmd: str, args) -> None:
    out_dir = getattr(args, "out_dir", None)
    if cmd == "start":
        print()
        print(f"Done. Review outputs in {out_dir}.")
        print("Start with run_summary.json and camilladsp_full.yaml.")
        print("If PipeWire did not pick the right devices, rerun with --output-target and/or --input-target.")
    elif cmd == "measure":
        print()
        print(f"Measurement saved in {out_dir}.")
        print(f"Next: headmatch fit --recording {Path(out_dir) / 'recording.wav'} --out-dir {Path(out_dir) / 'fit'}")
    elif cmd == "prepare-offline":
        print()
        print(f"Offline package saved in {out_dir}.")
        print("Record the sweep, copy the WAV to recording.wav, then run fit-offline.")
    elif cmd == "analyze":
        print()
        print(f"Analysis written to {out_dir}.")
        print("Review the CSVs, or run fit/fit-offline to build EQ.")
    elif cmd in {"fit", "fit-offline", "iterate"}:
        print()
        print(f"Done. Review outputs in {out_dir}.")
        print("Start with run_summary.json and camilladsp_full.yaml.")
    elif cmd == "clone-target":
        print()
        print(f"Clone target written to {args.out}.")
        print("Next: pass that CSV to fit, fit-offline, or start with --target-csv.")
    elif cmd == "tui":
        print()
        result = getattr(args, "tui_result", None)
        if getattr(result, "workflow", None) == "history":
            print(f"History browser finished. Review outputs in {result.out_dir}.")
            if getattr(result, "details", ""):
                print(f"Guide: {result.details}")
        else:
            print("Wizard finished. Reopen 'headmatch tui' any time for another guided run.")


def format_user_error(cmd: str, exc: ValueError) -> str:
    message = str(exc)
    if cmd == "clone-target":
        return (
            f"clone-target failed: {message}\n"
            "Check that both input CSVs include frequency and response columns, span 1 kHz, and that --out points to a new file."
        )
    if cmd in {"fit", "fit-offline", "start", "iterate"} and 'Target curve' in message:
        return (
            f"target CSV could not be used: {message}\n"
            "Use a target file that includes frequency + response data and spans 1 kHz."
        )
    if cmd in {"fit", "fit-offline", "start", "iterate"} and ('frequency column' in message or 'response column' in message):
        return (
            f"target CSV could not be read: {message}\n"
            "Expected a CSV with a frequency column such as frequency_hz/frequency/freq and a response column such as response_db/raw/target_db."
        )
    return message


def main(argv: list[str] | None = None) -> None:
    bootstrap = argparse.ArgumentParser(add_help=False)
    bootstrap.add_argument("--config", default=None)
    bootstrap_args, _ = bootstrap.parse_known_args(argv)
    config, config_path, created = load_or_create_config(bootstrap_args.config)

    parser = build_parser(config)
    args = parser.parse_args(argv)

    if not args.cmd:
        print_beginner_guide(parser)
        print()
        print(f"Config path: {config_path}")
        if created:
            print("Created a default config file with safe starter values.")
        raise SystemExit(0)

    from .analysis import analyze_measurement
    from .measure import (
        MeasurementPaths,
        OfflineMeasurementPlan,
        PipeWireDeviceConfig,
        prepare_offline_measurement,
        render_sweep_file,
        run_pipewire_measurement,
    )
    from .pipeline import build_clone_curve, iterative_measure_and_fit, process_single_measurement
    from .tui import run_tui

    try:
        if args.cmd == "tui":
            from sys import stdin, stdout
            args.tui_result = run_tui(stdin=stdin, stdout=stdout, config_loader=lambda: config)
        elif args.cmd == "start":
            print(f"Starting guided measurement workflow in {args.out_dir} ...")
            iterative_measure_and_fit(
                output_dir=args.out_dir,
                sweep_spec=spec_from_args(args),
                target_path=args.target_csv,
                output_target=args.output_target,
                input_target=args.input_target,
                iterations=args.iterations,
                max_filters=args.max_filters,
            )
        elif args.cmd == "render-sweep":
            render_sweep_file(spec_from_args(args), args.out)
        elif args.cmd == "measure":
            out_dir = Path(args.out_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            run_pipewire_measurement(
                spec_from_args(args),
                MeasurementPaths(out_dir / "sweep.wav", out_dir / "recording.wav"),
                PipeWireDeviceConfig(output_target=args.output_target, input_target=args.input_target),
            )
        elif args.cmd == "prepare-offline":
            out_dir = Path(args.out_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            prepare_offline_measurement(
                spec_from_args(args),
                OfflineMeasurementPlan(out_dir / "sweep.wav", out_dir / "measurement_plan.json", notes=args.notes),
            )
        elif args.cmd == "analyze":
            analyze_measurement(args.recording, spec_from_args(args), out_dir=args.out_dir)
        elif args.cmd == "fit":
            process_single_measurement(args.recording, args.out_dir, spec_from_args(args), target_path=args.target_csv, max_filters=args.max_filters)
        elif args.cmd == "fit-offline":
            process_single_measurement(args.recording, args.out_dir, spec_from_args(args), target_path=args.target_csv, max_filters=args.max_filters)
        elif args.cmd == "clone-target":
            build_clone_curve(args.source_csv, args.target_csv, args.out)
        elif args.cmd == "iterate":
            iterative_measure_and_fit(
                output_dir=args.out_dir,
                sweep_spec=spec_from_args(args),
                target_path=args.target_csv,
                output_target=args.output_target,
                input_target=args.input_target,
                iterations=args.iterations,
                max_filters=args.max_filters,
            )
    except ValueError as exc:
        parser.exit(2, f"Error: {format_user_error(args.cmd, exc)}\n")

    if args.cmd != 'tui':
        save_config(update_config_from_args(args, existing=config), config_path)
    print_next_steps(args.cmd, args)


if __name__ == "__main__":
    main()
