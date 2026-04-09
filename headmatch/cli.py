from __future__ import annotations

import argparse
import json
from pathlib import Path

from .contracts import FrontendRunSummary
from .troubleshooting import confidence_troubleshooting_steps

from .app_identity import get_app_identity
from .peq import FilterBudget
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


def positive_int(value: str) -> int:
    try:
        n = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid integer value: {value!r}") from exc
    if n <= 0:
        raise argparse.ArgumentTypeError(f"must be a positive integer, got {n}")
    return n


def add_filter_budget_args(p: argparse.ArgumentParser, config) -> None:
    p.add_argument("--max-filters", type=positive_int, default=config.max_filters, help="Number of EQ filters per channel. With --fill-policy up_to_n (default), this is the maximum. With --fill-policy exact_n, exactly this many filters are placed.")
    p.add_argument(
        "--filter-family",
        choices=("peq", "graphic_eq"),
        default="peq",
        help="Filter backend family: parametric PEQ or fixed-band GraphicEQ.",
    )
    p.add_argument(
        "--graphic-eq-profile",
        choices=("geq_10_band", "geq_31_band"),
        default=None,
        help="Fixed-band GraphicEQ profile when --filter-family graphic_eq is selected.",
    )
    p.add_argument(
        "--fill-policy",
        choices=("up_to_n", "exact_n"),
        default="up_to_n",
        help="How aggressively to spend the PEQ budget: conservative up-to-N or exact-count N.",
    )


def filter_budget_from_args(args) -> FilterBudget:
    return FilterBudget(
        family=args.filter_family,
        max_filters=args.max_filters,
        fill_policy=args.fill_policy,
        profile=args.graphic_eq_profile,
    ).normalized()


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
            "Beginner path: run 'headmatch start --out-dir session_01' for a guided "
            "measure-and-fit pass, or 'headmatch prepare-offline --out-dir session_01' "
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
            "Run one guided online measurement pass and export Equalizer APO and CamillaDSP EQ files. "
            "This is the easiest place to start."
        ),
    )
    add_common_sweep_args(p, config)
    p.add_argument("--out-dir", required=True, help="Folder for the sweep, recording, reports, and EQ export files.")
    p.add_argument("--target-csv", default=config.preferred_target_csv, help="Optional target curve CSV. If omitted, fit toward flat.")
    p.add_argument("--output-target", default=config.pipewire_output_target, help="Optional playback device name or ID. Run 'headmatch list-targets' to discover likely values.")
    p.add_argument("--input-target", default=config.pipewire_input_target, help="Optional capture device name or ID. Run 'headmatch list-targets' to discover likely values.")
    add_filter_budget_args(p, config)
    p.add_argument(
        "--iterations",
        type=positive_int,
        default=config.start_iterations,
        help="Number of online measure-and-fit passes. Default: 1 for a simple first run.",
    )
    p.add_argument(
        "--iteration-mode",
        choices=("independent", "average"),
        default="independent",
        help="Iteration strategy: independent (fit each pass separately) or average (average all passes, fit once).",
    )

    p = sub.add_parser("render-sweep", help="Generate a sweep WAV file.")
    add_common_sweep_args(p, config)
    p.add_argument("--out", required=True)

    p = sub.add_parser("measure", help="Play sweep and record the transfer.")
    add_common_sweep_args(p, config)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--output-target", default=config.pipewire_output_target, help="Playback device name or ID. Use 'headmatch list-targets' to see likely values.")
    p.add_argument("--input-target", default=config.pipewire_input_target, help="Capture device name or ID. Use 'headmatch list-targets' to see likely values.")

    p = sub.add_parser("prepare-offline", help="Create sweep + metadata for Zoom/H2n or SD-card recording workflows.")
    add_common_sweep_args(p, config)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--notes", default="")

    p = sub.add_parser("analyze", help="Analyze a recording WAV and write FR CSVs.")
    add_common_sweep_args(p, config)
    p.add_argument("--recording", required=True)
    p.add_argument("--out-dir", required=True)

    p = sub.add_parser("fit", help="Analyze a recording and build Equalizer APO and CamillaDSP EQ exports.", description="Analyze a recording, fit EQ, and export presets. The fit output includes a trust summary and clipping guidance when available.")
    add_common_sweep_args(p, config)
    p.add_argument("--recording", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--target-csv", default=config.preferred_target_csv)
    add_filter_budget_args(p, config)
    p.add_argument("--json", action="store_true", help="Print the run summary as JSON instead of the human-readable terminal summary.")
    p.add_argument("--show-clipping", action="store_true", help="Show detailed clipping assessment information in the terminal output.")

    p = sub.add_parser("search-headphone", help="Search community headphone databases for a model name.")
    p.add_argument("query", help="Headphone model name to search for.")

    p = sub.add_parser("fetch-curve", help="Download a published headphone FR curve from a URL.")
    p.add_argument("--url", required=True, help="URL to a raw CSV frequency response file.")
    p.add_argument("--out", required=True, help="Local path to save the downloaded curve.")

    p = sub.add_parser("import-apo", help="Import an Equalizer APO parametric preset and convert to other formats.")
    p.add_argument("--preset", required=True, help="Path to an Equalizer APO .txt parametric preset.")
    p.add_argument("--out-dir", required=True, help="Output directory for converted preset files.")

    p = sub.add_parser("refine-apo", help="Refine an imported APO preset against a new measurement.")
    p.add_argument("--preset", required=True, help="Path to an Equalizer APO .txt parametric preset to refine.")
    p.add_argument("--recording", required=True, help="Path to a recording WAV to fit against.")
    p.add_argument("--out-dir", required=True, help="Output directory for refined results.")
    p.add_argument("--target-csv", default=None, help="Target curve CSV (flat if omitted).")
    add_common_sweep_args(p, config)

    p = sub.add_parser("clone-target", help="Create a clone target curve from source and target FR CSVs.")
    p.add_argument("--source-csv", required=True)
    p.add_argument("--target-csv", required=True)
    p.add_argument(
        "--out",
        required=True,
        help="Write the clone target to a new CSV file. Do not point this at your source or target input file.",
    )


    p = sub.add_parser(
        "batch-fit",
        help="Fit multiple recordings from a batch manifest file.",
        description=(
            "Process every recording/target pair listed in a JSON manifest. "
            "Each entry gets its own output folder with the standard EQ exports. "
            "A consolidated batch_summary.json is written next to the manifest."
        ),
    )
    add_common_sweep_args(p, config)
    p.add_argument("--manifest", required=True, help="Path to a JSON batch manifest file.")
    add_filter_budget_args(p, config)

    p = sub.add_parser(
        "batch-template",
        help="Generate a starter batch manifest template.",
        description="Write a batch_manifest.json template with placeholder entries to help first-time users.",
    )
    p.add_argument("--out", default="batch_manifest.json", help="Output path for the template file.")
    p.add_argument("--entries", type=positive_int, default=3, help="Number of placeholder entries.")

    p = sub.add_parser(
        "history",
        help="Browse recent fit/iteration runs and review results.",
        description="List recent run summaries found under a folder tree.",
    )
    p.add_argument("--root", default=".", help="Root folder to search for run_summary.json files.")
    p.add_argument("--limit", type=positive_int, default=10, help="Maximum number of runs to show.")

    p = sub.add_parser(
        "compare-runs",
        help="Compare two recent runs side by side.",
        description="Show a side-by-side comparison table of the two most recent runs.",
    )
    p.add_argument("--root", default=".", help="Root folder to search for run_summary.json files.")

    p = sub.add_parser(
        "compare-ab",
        help="A/B compare two runs and export paired presets for quick switching.",
        description=(
            "Compare two run directories side by side and export both presets "
            "into a single folder with A_/B_ prefixes for easy A/B testing."
        ),
    )
    p.add_argument("--run-a", required=True, help="Path to the first run directory.")
    p.add_argument("--run-b", required=True, help="Path to the second run directory.")
    p.add_argument("--label-a", default="A", help="Label for the first run (default: A).")
    p.add_argument("--label-b", default="B", help="Label for the second run (default: B).")
    p.add_argument("--out-dir", required=True, help="Output directory for comparison presets.")

    sub.add_parser(
        "list-targets",
        help="List likely audio playback and capture targets.",
        description=(
            "Inspect audio devices and print beginner-friendly suggestions for "
            "--output-target and --input-target."
        ),
    )

    p = sub.add_parser("iterate", help="Measure -> fit -> export Equalizer APO and CamillaDSP files, repeated.")
    add_common_sweep_args(p, config)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--target-csv", default=config.preferred_target_csv)
    p.add_argument("--output-target", default=config.pipewire_output_target, help="Playback device name or ID. Use 'headmatch list-targets' to see likely values.")
    p.add_argument("--input-target", default=config.pipewire_input_target, help="Capture device name or ID. Use 'headmatch list-targets' to see likely values.")
    p.add_argument("--iterations", type=positive_int, default=config.iterate_iterations)
    p.add_argument(
        "--iteration-mode",
        choices=("independent", "average"),
        default="independent",
        help="Iteration strategy: independent (fit each pass separately) or average (average all passes, fit once).",
    )
    add_filter_budget_args(p, config)

    sub.add_parser(
        "doctor",
        help="Check whether the local HeadMatch environment looks ready.",
        description="Run a small beginner-friendly readiness check for config, audio tools, and device discovery.",
    )

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
    print("1) First try: headmatch start --out-dir session_01")
    print("   This runs one online measurement pass and exports Equalizer APO and CamillaDSP EQ files.")
    print()
    print("2) If your recorder is more reliable offline:")
    print("   headmatch prepare-offline --out-dir session_01")
    print("   ...record the sweep, then run:")
    print("   headmatch fit --recording session_01/recording.wav --out-dir session_01/fit")
    print()
    print("Not sure your setup is ready? Run: headmatch doctor")
    print("Need device names? Run: headmatch list-targets")
    print("Developer commands are still available below.")
    print()
    parser.print_help()


def _confidence_display(label: str) -> str:
    return label.replace("_", " ").title()


def _run_summary_path(cmd: str, args) -> Path | None:
    out_dir = getattr(args, "out_dir", None)
    if not out_dir:
        return None
    base = Path(out_dir)
    if cmd in {"fit"}:
        return base / "run_summary.json"
    if cmd in {"start", "iterate"}:
        iteration_mode = getattr(args, "iteration_mode", "independent")
        if iteration_mode == "average":
            return base / "run_summary.json"
        iterations = getattr(args, "iterations", None)
        if isinstance(iterations, int) and iterations > 0:
            return base / f"iter_{iterations:02d}" / "run_summary.json"
    return None


def _verdict_line(confidence) -> str:
    """Single-line verdict with optional ANSI color when stdout is a TTY."""
    import sys
    is_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    if confidence.label == 'high':
        prefix = '\033[32m✓\033[0m' if is_tty else '✓'
        return f"{prefix} This run looks trustworthy."
    elif confidence.label == 'medium':
        prefix = '\033[33m⚠\033[0m' if is_tty else '⚠'
        return f"{prefix} Moderate confidence — review the details below."
    else:
        prefix = '\033[31m✗\033[0m' if is_tty else '✗'
        return f"{prefix} Low confidence — check the details below."


def print_run_confidence(cmd: str, args) -> None:
    summary_path = _run_summary_path(cmd, args)
    if summary_path is None or not summary_path.exists():
        return

    try:
        summary = FrontendRunSummary.from_dict(json.loads(summary_path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return

    confidence = summary.confidence
    print()
    print(_verdict_line(confidence))
    print(
        f"Confidence: {_confidence_display(confidence.label)} ({confidence.score}/100) — {confidence.headline}"
    )
    if confidence.interpretation:
        print(confidence.interpretation)
    for warning in confidence.warnings[:3]:
        print(f"Warning: {warning}")
    steps = confidence_troubleshooting_steps(confidence)
    if steps:
        print("Troubleshooting:")
        for step in steps:
            print(f"- {step}")


def _clipping_verdict_line(assessment) -> str:
    if assessment is None:
        return "No clipping assessment available."
    if assessment.get("will_clip"):
        return "⚠ EQ clipping detected — preamp reduction is recommended."
    return "✓ No EQ clipping detected."


def print_clipping_summary(summary: FrontendRunSummary, *, detailed: bool = False) -> None:
    assessment = summary.eq_clipping_assessment
    if not isinstance(assessment, dict):
        return

    print()
    print(_clipping_verdict_line(assessment))
    preamp_db = assessment.get("preamp_db")
    if preamp_db is None:
        preamp_db = assessment.get("total_preamp_db")
    print(f"Preamp recommendation: {float(preamp_db):.1f} dB")
    peak_boost = max(float(assessment.get("left_peak_boost_db", 0.0)), float(assessment.get("right_peak_boost_db", 0.0)))
    print(f"Max boost level: {peak_boost:.1f} dB")
    headroom = float(assessment.get("headroom_loss_db", 0.0))
    if headroom > 12:
        print(f"Warning: severe headroom loss ({headroom:.1f} dB).")
    elif headroom > 6:
        print(f"Warning: moderate headroom loss ({headroom:.1f} dB).")
    if detailed:
        print("Detailed clipping breakdown:")
        print(f"- Left peak boost: {float(assessment.get('left_peak_boost_db', 0.0)):+.1f} dB")
        print(f"- Right peak boost: {float(assessment.get('right_peak_boost_db', 0.0)):+.1f} dB")
        print(f"- Left preamp: {float(assessment.get('left_preamp_db', preamp_db)):.1f} dB")
        print(f"- Right preamp: {float(assessment.get('right_preamp_db', preamp_db)):.1f} dB")
        if assessment.get("quality_concern"):
            print(f"- Note: {assessment['quality_concern']}")


def print_next_steps(cmd: str, args) -> None:
    out_dir = getattr(args, "out_dir", None)
    if cmd == "start":
        print_run_confidence(cmd, args)
        print()
        print(f"Done. Review outputs in {out_dir}.")
        print("Start with run_summary.json, then use equalizer_apo.txt or camilladsp_full.yaml.")
        print("If the wrong devices were used, run 'headmatch list-targets' and rerun with --output-target and/or --input-target.")
    elif cmd == "measure":
        print()
        print(f"Measurement saved in {out_dir}.")
        print(f"Next: headmatch fit --recording {Path(out_dir) / 'recording.wav'} --out-dir {Path(out_dir) / 'fit'}")
    elif cmd == "prepare-offline":
        print()
        print(f"Offline package saved in {out_dir}.")
        print("Record the sweep, copy the WAV to recording.wav, then run fit.")
    elif cmd == "analyze":
        print()
        print(f"Analysis written to {out_dir}.")
        print("Review the CSVs, or run fit to build EQ.")
    elif cmd in {"fit", "iterate"}:
        print_run_confidence(cmd, args)
        summary_path = _run_summary_path(cmd, args)
        if summary_path is not None and summary_path.exists():
            try:
                summary = FrontendRunSummary.from_dict(json.loads(summary_path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
                summary = None
            if summary is not None:
                print_clipping_summary(summary, detailed=getattr(args, "show_clipping", False))
        print()
        print(f"Done. Review outputs in {out_dir}.")
        print("Start with run_summary.json, then use equalizer_apo.txt or camilladsp_full.yaml.")
    elif cmd == "clone-target":
        print()
        print(f"Clone target written to {args.out}.")
        print("Next: pass that CSV to fit, fit, or start with --target-csv.")
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
    if cmd in {"fit", "start", "iterate"} and 'Target curve' in message:
        return (
            f"target CSV could not be used: {message}\n"
            "Use a target file that includes frequency + response data and spans 1 kHz."
        )
    if cmd in {"fit", "start", "iterate"} and ('frequency column' in message or 'response column' in message):
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
        collect_doctor_checks,
        format_doctor_report,
        format_pipewire_targets,
        list_pipewire_targets,
        prepare_offline_measurement,
        render_sweep_file,
        run_pipewire_measurement,
    )
    from .pipeline import build_clone_curve, iterative_measure_and_fit, process_single_measurement
    from .tui import run_tui

    try:
        if args.cmd == "tui":
            from sys import stdin, stdout
            args.tui_result = run_tui(stdin=stdin, stdout=stdout, config_loader=lambda path=None: load_or_create_config(bootstrap_args.config or path), config_path=bootstrap_args.config)
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
                filter_budget=filter_budget_from_args(args),
                iteration_mode=getattr(args, 'iteration_mode', 'independent'),
            )
        elif args.cmd == "render-sweep":
            render_sweep_file(spec_from_args(args), args.out)
        elif args.cmd == "list-targets":
            print(format_pipewire_targets(list_pipewire_targets()))
        elif args.cmd == "create-shortcut":
            from .desktop import create_shortcut, find_gui_binary
            gui = find_gui_binary()
            if gui:
                path = create_shortcut(gui)
                print(f"Desktop shortcut created: {path}")
                print(f"Using GUI binary: {gui}")
            else:
                print("Could not find headmatch-gui. Is HeadMatch installed?")
        elif args.cmd == "remove-shortcut":
            from .desktop import remove_shortcut
            if remove_shortcut():
                print("Desktop shortcut removed.")
            else:
                print("No desktop shortcut found.")
        elif args.cmd == "doctor":
            from .desktop import shortcut_exists, find_gui_binary
            print(format_doctor_report(collect_doctor_checks(config_path, config), config_path=config_path))
            gui = find_gui_binary()
            if gui and not shortcut_exists():
                print(f"\nTip: Run 'headmatch create-shortcut' to add HeadMatch to your desktop launcher.")
                print(f"     (Found GUI at: {gui})")
            elif shortcut_exists():
                print(f"\nDesktop shortcut: installed ✓")
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
            process_single_measurement(args.recording, args.out_dir, spec_from_args(args), target_path=args.target_csv, max_filters=args.max_filters, filter_budget=filter_budget_from_args(args))
            if getattr(args, "json", False):
                summary_path = Path(args.out_dir) / "run_summary.json"
                try:
                    summary = FrontendRunSummary.from_dict(json.loads(summary_path.read_text(encoding="utf-8")))
                    print(json.dumps(summary.to_dict(), indent=2, sort_keys=True))
                except Exception:
                    pass
        elif args.cmd == "search-headphone":
            from .headphone_db import search_headphone
            results = search_headphone(args.query)
            if not results:
                print(f"No matches for '{args.query}'. Try a broader search or check your network connection.")
            else:
                print(f"Found {len(results)} match{'es' if len(results) != 1 else ''} for '{args.query}':\n")
                for entry in results[:25]:
                    print(f"  {entry.name}")
                    print(f"    Source: {entry.source} ({entry.form_factor})")
                    print(f"    Fetch:  headmatch fetch-curve --url \"{entry.raw_csv_url}\" --out \"{entry.name}.csv\"")
                    print()
                if len(results) > 25:
                    print(f"  ... and {len(results) - 25} more. Narrow your search for fewer results.")
        elif args.cmd == "fetch-curve":
            from .headphone_db import fetch_curve_from_url
            out = fetch_curve_from_url(args.url, args.out)
            print(f"Saved to {out}")
        elif args.cmd == "import-apo":
            from .apo_import import load_apo_preset
            from .exporters import (
                export_camilladsp_filters_yaml,
                export_camilladsp_filter_snippet_yaml,
                export_equalizer_apo_parametric_txt,
            )
            left_bands, right_bands = load_apo_preset(args.preset)
            print(f"Imported {len(left_bands)} left + {len(right_bands)} right filters from {args.preset}")
            out_dir = Path(args.out_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            export_equalizer_apo_parametric_txt(out_dir / 'equalizer_apo.txt', left_bands, right_bands)
            export_camilladsp_filters_yaml(out_dir / 'camilladsp_full.yaml', left_bands, right_bands)
            export_camilladsp_filter_snippet_yaml(out_dir / 'camilladsp_filters_only.yaml', left_bands, right_bands)
            print(f"Exported to {out_dir}: equalizer_apo.txt, camilladsp_full.yaml, camilladsp_filters_only.yaml")
        elif args.cmd == "refine-apo":
            from .apo_refine import refine_apo_preset
            report = refine_apo_preset(
                preset_path=args.preset,
                recording_wav=args.recording,
                sweep_spec=spec_from_args(args),
                out_dir=args.out_dir,
                target_path=args.target_csv,
            )
            orig = report.get('original_error', {})
            print(f"Refined preset from {args.preset}")
            print(f"  Before: L {orig.get('left_rms', 0):.2f} dB RMS, R {orig.get('right_rms', 0):.2f} dB RMS")
            print(f"  After:  L {report['predicted_left_rms_error_db']:.2f} dB RMS, R {report['predicted_right_rms_error_db']:.2f} dB RMS")
            print(f"  Output: {args.out_dir}")
        elif args.cmd == "clone-target":
            build_clone_curve(args.source_csv, args.target_csv, args.out)
        elif args.cmd == "batch-fit":
            from .batch import run_batch_fit
            def _batch_progress(current, total, label):
                print(f"  [{current}/{total}] {label} ...")
            print(f"Running batch fit from {args.manifest} ...")
            results = run_batch_fit(
                args.manifest,
                spec_from_args(args),
                max_filters=args.max_filters,
                filter_budget=filter_budget_from_args(args),
                on_progress=_batch_progress,
            )
            succeeded = sum(1 for r in results if r.success)
            failed = sum(1 for r in results if not r.success)
            print(f"Batch complete: {succeeded} succeeded, {failed} failed out of {len(results)}.")
            for r in results:
                if r.success:
                    print(f"  ✓ {r.label}: L={r.predicted_left_rms_error_db:.2f} R={r.predicted_right_rms_error_db:.2f} dB RMS ({r.confidence_label})")
                else:
                    print(f"  ✗ {r.label}: {r.error}")
        elif args.cmd == "batch-template":
            from .batch import generate_manifest_template
            out = generate_manifest_template(args.out, num_entries=args.entries)
            print(f"Template written to {out}")
            print("Edit the entries array with your recording paths, output folders, and target CSVs.")
        elif args.cmd == "history":
            from .history import load_recent_runs, read_results_guide
            runs = load_recent_runs(args.root, limit=args.limit)
            if not runs:
                print(f"No run_summary.json files found under {args.root}.")
                print("Run 'headmatch start' or 'headmatch fit' first.")
            else:
                print(f"Recent runs under {args.root}:")
                print()
                for i, entry in enumerate(runs, 1):
                    s = entry.summary
                    conf = s.confidence
                    print(f"  {i}) [{conf.label.upper():>6s} {conf.score:3d}/100] {s.kind} | {s.out_dir}")
                    print(f"     target={s.target} filters L/R={s.filters.left}/{s.filters.right}")
                    err = s.predicted_error_db
                    print(f"     error: L rms={err.left_rms:.2f} R rms={err.right_rms:.2f} dB")
                    print()
        elif args.cmd == "compare-runs":
            from .history import load_recent_runs, build_run_comparison
            runs = load_recent_runs(args.root, limit=2)
            if len(runs) < 2:
                print(f"Need at least 2 runs under {args.root} to compare. Found {len(runs)}.")
            else:
                comparison = build_run_comparison(runs)
                if comparison is None:
                    print("Could not build comparison.")
                else:
                    print(f"Comparing:")
                    print(f"  A: {comparison.left_entry.summary.out_dir}")
                    print(f"  B: {comparison.right_entry.summary.out_dir}")
                    print()
                    max_label = max(len(f.label) for f in comparison.fields)
                    for field in comparison.fields:
                        print(f"  {field.label:<{max_label}s}  A: {field.left}")
                        print(f"  {' ':<{max_label}s}  B: {field.right}")
                        print()
        elif args.cmd == "compare-ab":
            from .ab_compare import build_comparison_pair, export_ab_comparison, format_comparison_table
            pair = build_comparison_pair(
                args.run_a, args.run_b,
                label_a=args.label_a, label_b=args.label_b,
            )
            print(format_comparison_table(pair))
            print()
            export = export_ab_comparison(pair, args.out_dir)
            print(f"Presets exported to {export.output_dir}")
            print(f"  {export.preset_a_apo.name}, {export.preset_b_apo.name}")
            print(f"  {export.preset_a_cdsp.name}, {export.preset_b_cdsp.name}")
            print(f"  {export.comparison_json.name}")
        elif args.cmd == "iterate":
            iterative_measure_and_fit(
                output_dir=args.out_dir,
                sweep_spec=spec_from_args(args),
                target_path=args.target_csv,
                output_target=args.output_target,
                input_target=args.input_target,
                iterations=args.iterations,
                max_filters=args.max_filters,
                filter_budget=filter_budget_from_args(args),
                iteration_mode=getattr(args, 'iteration_mode', 'independent'),
            )
    except ValueError as exc:
        parser.exit(2, f"Error: {format_user_error(args.cmd, exc)}\n")

    if args.cmd not in {'doctor', 'tui', 'list-targets'} and not (args.cmd == "fit" and getattr(args, "json", False)):
        try:
            save_config(update_config_from_args(args, existing=config), config_path)
        except OSError:
            pass
    if args.cmd == "fit" and getattr(args, "json", False):
        return
    print_next_steps(args.cmd, args)


if __name__ == "__main__":
    main()
