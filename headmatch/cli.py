from __future__ import annotations

import argparse
from pathlib import Path


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


def add_common_sweep_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--sample-rate", type=int, default=48000)
    p.add_argument("--duration", type=parse_seconds, default=8.0)
    p.add_argument("--f-start", type=float, default=20.0)
    p.add_argument("--f-end", type=float, default=22000.0)
    p.add_argument("--pre-silence", type=parse_seconds, default=0.5)
    p.add_argument("--post-silence", type=parse_seconds, default=1.0)
    p.add_argument("--amplitude", type=float, default=0.2)


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="headmatch",
        description="Beginner-first headphone measurement and EQ fitting.",
        epilog=(
            "Beginner path: run 'headmatch start --out-dir out/session_01' for a guided "
            "measure-and-fit pass, or 'headmatch prepare-offline --out-dir out/session_01' "
            "if you want to record first and import later."
        ),
    )
    sub = parser.add_subparsers(dest="cmd")

    p = sub.add_parser(
        "start",
        help="Beginner-first: measure once and build an EQ preset.",
        description=(
            "Run one guided online measurement pass and export CamillaDSP EQ files. "
            "This is the easiest place to start."
        ),
    )
    add_common_sweep_args(p)
    p.add_argument("--out-dir", required=True, help="Folder for the sweep, recording, reports, and YAML exports.")
    p.add_argument("--target-csv", default=None, help="Optional target curve CSV. If omitted, fit toward flat.")
    p.add_argument("--output-target", default=None, help="Optional PipeWire playback node match string.")
    p.add_argument("--input-target", default=None, help="Optional PipeWire capture node match string.")
    p.add_argument("--max-filters", type=int, default=8, help="Maximum PEQ filters per channel.")
    p.add_argument(
        "--iterations",
        type=int,
        default=DEFAULT_START_ITERATIONS,
        help="Number of online measure-and-fit passes. Default: 1 for a simple first run.",
    )

    p = sub.add_parser("render-sweep", help="Generate a sweep WAV file.")
    add_common_sweep_args(p)
    p.add_argument("--out", required=True)

    p = sub.add_parser("measure", help="Play sweep via PipeWire and record the transfer.")
    add_common_sweep_args(p)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--output-target", default=None)
    p.add_argument("--input-target", default=None)

    p = sub.add_parser("prepare-offline", help="Create sweep + metadata for Zoom/H2n or SD-card recording workflows.")
    add_common_sweep_args(p)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--notes", default="")

    p = sub.add_parser("analyze", help="Analyze a recording WAV and write FR CSVs.")
    add_common_sweep_args(p)
    p.add_argument("--recording", required=True)
    p.add_argument("--out-dir", required=True)

    p = sub.add_parser("fit", help="Analyze a recording and build CamillaDSP EQ.")
    add_common_sweep_args(p)
    p.add_argument("--recording", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--target-csv", default=None)
    p.add_argument("--max-filters", type=int, default=8)

    p = sub.add_parser("fit-offline", help="Analyze an imported offline recording and build CamillaDSP EQ.")
    add_common_sweep_args(p)
    p.add_argument("--recording", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--target-csv", default=None)
    p.add_argument("--max-filters", type=int, default=8)

    p = sub.add_parser("clone-target", help="Create a clone target curve from source and target FR CSVs.")
    p.add_argument("--source-csv", required=True)
    p.add_argument("--target-csv", required=True)
    p.add_argument("--out", required=True)

    p = sub.add_parser("iterate", help="Measure -> fit -> export, repeated.")
    add_common_sweep_args(p)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--target-csv", default=None)
    p.add_argument("--output-target", default=None)
    p.add_argument("--input-target", default=None)
    p.add_argument("--iterations", type=int, default=2)
    p.add_argument("--max-filters", type=int, default=8)
    return parser


def print_beginner_guide(parser: argparse.ArgumentParser) -> None:
    print("headmatch beginner path")
    print("=======================")
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


def main(argv: list[str] | None = None) -> None:
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

    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.cmd:
        print_beginner_guide(parser)
        raise SystemExit(0)

    if args.cmd == "start":
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

    print_next_steps(args.cmd, args)


if __name__ == "__main__":
    main()
