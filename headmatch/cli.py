from __future__ import annotations

import argparse
from pathlib import Path

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
from .signals import SweepSpec


def add_common_sweep_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--sample-rate", type=int, default=48000)
    p.add_argument("--duration", type=float, default=8.0)
    p.add_argument("--f-start", type=float, default=20.0)
    p.add_argument("--f-end", type=float, default=22000.0)
    p.add_argument("--pre-silence", type=float, default=0.5)
    p.add_argument("--post-silence", type=float, default=1.0)
    p.add_argument("--amplitude", type=float, default=0.2)


def spec_from_args(args) -> SweepSpec:
    return SweepSpec(
        sample_rate=args.sample_rate,
        duration_s=args.duration,
        f_start=args.f_start,
        f_end=args.f_end,
        pre_silence_s=args.pre_silence,
        post_silence_s=args.post_silence,
        amplitude=args.amplitude,
    )


def main() -> None:
    parser = argparse.ArgumentParser(prog="headmatch")
    sub = parser.add_subparsers(dest="cmd", required=True)

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

    args = parser.parse_args()
    if args.cmd == "render-sweep":
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


if __name__ == "__main__":
    main()
