from __future__ import annotations

import argparse
import queue
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .app_identity import get_app_identity
from .contracts import FrontendConfig
from .measure import OfflineMeasurementPlan, prepare_offline_measurement
from .pipeline import iterative_measure_and_fit, process_single_measurement
from .settings import load_or_create_config
from .signals import SweepSpec


@dataclass(frozen=True)
class NavigationItem:
    key: str
    label: str
    description: str


@dataclass(frozen=True)
class GuiState:
    version_display: str
    config_path: Path
    config_created: bool
    current_view: str
    default_output_dir: str
    preferred_target_csv: str
    pipewire_output_target: str
    pipewire_input_target: str
    start_iterations: int
    max_filters: int
    sample_rate: int
    duration_s: float
    f_start_hz: float
    f_end_hz: float
    pre_silence_s: float
    post_silence_s: float
    amplitude: float


ConfigLoader = Callable[[str | Path | None], tuple[FrontendConfig, Path, bool]]
OnlineRunner = Callable[..., list[dict]]
OfflinePrepareRunner = Callable[[SweepSpec, OfflineMeasurementPlan], dict]
OfflineFitRunner = Callable[..., dict]


NAV_ITEMS: tuple[NavigationItem, ...] = (
    NavigationItem("home", "Home", "See the saved defaults and choose a workflow."),
    NavigationItem("measure-online", "Measure now", "Guided online measurement with PipeWire playback and capture."),
    NavigationItem("prepare-offline", "Prepare offline", "Recorder-first package export plus offline fit import."),
    NavigationItem("history", "History", "Browse recent runs and open the generated guides."),
)


ONLINE_STEPS = (
    "Check the output folder and saved PipeWire targets.",
    "Press Start when your measurement rig is ready.",
    "HeadMatch will run the shared online pipeline and then show the output folder.",
)


OFFLINE_STEPS = (
    "Prepare a sweep package if you need to record with a handheld recorder first.",
    "After recording, point the GUI at the WAV file and run the offline fit.",
    "Both actions reuse the same shared sweep and fitting pipeline as the CLI and TUI.",
)


def load_gui_state(
    config_path: str | Path | None = None,
    *,
    config_loader: ConfigLoader = load_or_create_config,
) -> GuiState:
    identity = get_app_identity()
    config, resolved_path, created = config_loader(config_path)
    return GuiState(
        version_display=identity.version_display,
        config_path=Path(resolved_path),
        config_created=created,
        current_view="home",
        default_output_dir=config.default_output_dir or "out/session_01",
        preferred_target_csv=config.preferred_target_csv or "",
        pipewire_output_target=config.pipewire_output_target or "",
        pipewire_input_target=config.pipewire_input_target or "",
        start_iterations=config.start_iterations,
        max_filters=config.max_filters,
        sample_rate=config.sample_rate,
        duration_s=config.duration_s,
        f_start_hz=config.f_start_hz,
        f_end_hz=config.f_end_hz,
        pre_silence_s=config.pre_silence_s,
        post_silence_s=config.post_silence_s,
        amplitude=config.amplitude,
    )


class HeadMatchGuiApp:
    def __init__(
        self,
        root,
        state: GuiState,
        *,
        online_runner: OnlineRunner = iterative_measure_and_fit,
        offline_prepare_runner: OfflinePrepareRunner = prepare_offline_measurement,
        offline_fit_runner: OfflineFitRunner = process_single_measurement,
    ):
        import tkinter as tk
        from tkinter import ttk

        self.root = root
        self.state = state
        self._ttk = ttk
        self._online_runner = online_runner
        self._offline_prepare_runner = offline_prepare_runner
        self._offline_fit_runner = offline_fit_runner
        self._task_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._active_task_name: str | None = None
        self._last_completion_steps: tuple[str, ...] = ()

        self.current_view = tk.StringVar(master=root, value=state.current_view)
        self.output_dir_var = tk.StringVar(master=root, value=state.default_output_dir)
        self.target_csv_var = tk.StringVar(master=root, value=state.preferred_target_csv)
        self.output_target_var = tk.StringVar(master=root, value=state.pipewire_output_target)
        self.input_target_var = tk.StringVar(master=root, value=state.pipewire_input_target)
        self.iterations_var = tk.StringVar(master=root, value=str(state.start_iterations))
        self.max_filters_var = tk.StringVar(master=root, value=str(state.max_filters))
        self.history_root_var = tk.StringVar(master=root, value=str(Path(state.default_output_dir).expanduser().parent))
        self.offline_recording_var = tk.StringVar(master=root, value="")
        self.offline_fit_output_var = tk.StringVar(master=root, value=str(Path(state.default_output_dir).expanduser() / "fit"))
        self.offline_notes_var = tk.StringVar(master=root, value="")
        self.progress_title_var = tk.StringVar(master=root, value="")
        self.progress_body_var = tk.StringVar(master=root, value="")
        self.completion_title_var = tk.StringVar(master=root, value="")
        self.completion_body_var = tk.StringVar(master=root, value="")
        self.content = None

        self.root.title(f"HeadMatch {state.version_display}")
        self.root.minsize(920, 580)
        self._build_shell()
        self.show_view(state.current_view)

    def build_history_selection(self):
        from .history import build_history_selection

        return build_history_selection(self.history_root_var.get(), self.state.config_path.parent)

    def _build_shell(self) -> None:
        ttk = self._ttk
        root = self.root
        root.columnconfigure(1, weight=1)
        root.rowconfigure(1, weight=1)

        header = ttk.Frame(root, padding=(20, 18, 20, 12))
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="HeadMatch", font=("TkDefaultFont", 18, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(header, text=f"Version {self.state.version_display}", font=("TkDefaultFont", 12, "bold")).grid(row=0, column=1, sticky="e")
        ttk.Label(header, text="A guided desktop shell for headphone measurement, fitting, and beginner-friendly review.").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(6, 0)
        )

        nav = ttk.Frame(root, padding=(20, 8, 12, 20))
        nav.grid(row=1, column=0, sticky="nsw")
        ttk.Label(nav, text="Workflows", font=("TkDefaultFont", 11, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 8))
        for idx, item in enumerate(NAV_ITEMS, start=1):
            ttk.Button(nav, text=f"{item.label}\n{item.description}", command=lambda key=item.key: self.show_view(key), width=28).grid(
                row=idx, column=0, sticky="ew", pady=4
            )

        self.content = ttk.Frame(root, padding=(12, 8, 20, 20))
        self.content.grid(row=1, column=1, sticky="nsew")
        self.content.columnconfigure(0, weight=1)

    def show_view(self, key: str) -> None:
        self.current_view.set(key)
        for child in self.content.winfo_children():
            child.destroy()
        if key == "home":
            self._render_home()
            return
        if key == "measure-online":
            self._render_online_wizard()
            return
        if key == "prepare-offline":
            self._render_offline_wizard()
            return
        if key == "history":
            self._render_history()
            return
        raise KeyError(key)

    def _render_home(self) -> None:
        ttk = self._ttk
        frame = self.content
        ttk.Label(frame, text="Main screen", font=("TkDefaultFont", 15, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(
            frame,
            text=(
                "Choose the online path if PipeWire playback/capture is working today, or the offline path if you want to "
                "record first and import the WAV later. The saved defaults below preload both workflows."
            ),
            wraplength=620,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(8, 16))
        card = ttk.LabelFrame(frame, text="Saved defaults", padding=16)
        card.grid(row=2, column=0, sticky="ew")
        card.columnconfigure(1, weight=1)
        self._add_readonly_row(card, 0, "Output folder", self.output_dir_var)
        self._add_readonly_row(card, 1, "Playback target", self.output_target_var)
        self._add_readonly_row(card, 2, "Capture target", self.input_target_var)
        self._add_readonly_row(card, 3, "Target CSV", self.target_csv_var)
        self._add_readonly_row(card, 4, "Iterations", self.iterations_var)
        self._add_readonly_row(card, 5, "Max PEQ filters", self.max_filters_var)
        note = f"Config file: {self.state.config_path}"
        if self.state.config_created:
            note += " (created with starter defaults on this launch)"
        ttk.Label(frame, text=note, wraplength=620, justify="left").grid(row=3, column=0, sticky="w", pady=(12, 0))

    def _render_online_wizard(self) -> None:
        ttk = self._ttk
        frame = self.content
        ttk.Label(frame, text="Online measurement wizard", font=("TkDefaultFont", 15, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(
            frame,
            text="Use this when PipeWire playback and capture are available now. The GUI keeps the first run simple and uses the shared measure → analyze → fit pipeline.",
            wraplength=650,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(8, 12))
        steps = ttk.LabelFrame(frame, text="What happens", padding=16)
        steps.grid(row=2, column=0, sticky="ew")
        for idx, step in enumerate(ONLINE_STEPS):
            ttk.Label(steps, text=f"{idx + 1}. {step}", wraplength=620, justify="left").grid(row=idx, column=0, sticky="w", pady=2)

        form = ttk.LabelFrame(frame, text="Run details", padding=16)
        form.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        form.columnconfigure(1, weight=1)
        self._add_entry_row(form, 0, "Output folder", self.output_dir_var)
        self._add_entry_row(form, 1, "Playback target", self.output_target_var)
        self._add_entry_row(form, 2, "Capture target", self.input_target_var)
        self._add_entry_row(form, 3, "Target CSV (optional)", self.target_csv_var)
        self._add_entry_row(form, 4, "Iterations", self.iterations_var)
        self._add_entry_row(form, 5, "Max PEQ filters", self.max_filters_var)

        actions = ttk.Frame(frame, padding=(0, 12, 0, 0))
        actions.grid(row=4, column=0, sticky="w")
        ttk.Button(actions, text="Start guided measurement", command=self.start_online_measurement).grid(row=0, column=0, sticky="w")
        ttk.Label(actions, text="Make sure your headphone rig is connected and quiet before you start.").grid(
            row=0, column=1, sticky="w", padx=(12, 0)
        )

    def _render_offline_wizard(self) -> None:
        ttk = self._ttk
        frame = self.content
        ttk.Label(frame, text="Offline measurement wizard", font=("TkDefaultFont", 15, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(
            frame,
            text="Use this when a handheld recorder is more reliable than live capture. First prepare the sweep package, then come back and fit the imported WAV.",
            wraplength=650,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(8, 12))
        steps = ttk.LabelFrame(frame, text="What happens", padding=16)
        steps.grid(row=2, column=0, sticky="ew")
        for idx, step in enumerate(OFFLINE_STEPS):
            ttk.Label(steps, text=f"{idx + 1}. {step}", wraplength=620, justify="left").grid(row=idx, column=0, sticky="w", pady=2)

        prep = ttk.LabelFrame(frame, text="Step A — prepare the recorder package", padding=16)
        prep.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        prep.columnconfigure(1, weight=1)
        self._add_entry_row(prep, 0, "Package folder", self.output_dir_var)
        self._add_entry_row(prep, 1, "Notes (optional)", self.offline_notes_var)
        ttk.Button(prep, text="Write sweep package", command=self.start_offline_prepare).grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

        fit = ttk.LabelFrame(frame, text="Step B — fit an imported recording", padding=16)
        fit.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        fit.columnconfigure(1, weight=1)
        self._add_entry_row(fit, 0, "Recorded WAV", self.offline_recording_var)
        self._add_entry_row(fit, 1, "Fit output folder", self.offline_fit_output_var)
        self._add_entry_row(fit, 2, "Target CSV (optional)", self.target_csv_var)
        self._add_entry_row(fit, 3, "Max PEQ filters", self.max_filters_var)
        ttk.Button(fit, text="Fit imported recording", command=self.start_offline_fit).grid(row=4, column=0, columnspan=2, sticky="w", pady=(8, 0))

    def _render_progress(self) -> None:
        ttk = self._ttk
        frame = self.content
        ttk.Label(frame, text=self.progress_title_var.get(), font=("TkDefaultFont", 15, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(frame, text=self.progress_body_var.get(), wraplength=650, justify="left").grid(row=1, column=0, sticky="w", pady=(8, 12))
        note = ttk.LabelFrame(frame, text="What to do now", padding=16)
        note.grid(row=2, column=0, sticky="ew")
        ttk.Label(
            note,
            text="Keep this window open while the shared pipeline runs. When the task finishes, this screen will switch to a completion summary automatically.",
            wraplength=620,
            justify="left",
        ).grid(row=0, column=0, sticky="w")

    def _render_completion(self) -> None:
        ttk = self._ttk
        frame = self.content
        ttk.Label(frame, text=self.completion_title_var.get(), font=("TkDefaultFont", 15, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(frame, text=self.completion_body_var.get(), wraplength=650, justify="left").grid(row=1, column=0, sticky="w", pady=(8, 12))
        card = ttk.LabelFrame(frame, text="Next steps", padding=16)
        card.grid(row=2, column=0, sticky="ew")
        for idx, step in enumerate(self._last_completion_steps):
            ttk.Label(card, text=f"- {step}", wraplength=620, justify="left").grid(row=idx, column=0, sticky="w", pady=2)
        actions = ttk.Frame(frame, padding=(0, 12, 0, 0))
        actions.grid(row=3, column=0, sticky="w")
        ttk.Button(actions, text="Back to Home", command=lambda: self.show_view("home")).grid(row=0, column=0, sticky="w")
        ttk.Button(actions, text="Open History", command=lambda: self.show_view("history")).grid(row=0, column=1, sticky="w", padx=(12, 0))

    def _render_history(self) -> None:
        ttk = self._ttk
        frame = self.content
        ttk.Label(frame, text="History", font=("TkDefaultFont", 15, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(
            frame,
            text="Browse recent runs by scanning for run_summary.json files. This uses the same shared history loader as the terminal UI.",
            wraplength=620,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(8, 12))

        controls = ttk.LabelFrame(frame, text="Search", padding=16)
        controls.grid(row=2, column=0, sticky="ew")
        controls.columnconfigure(1, weight=1)
        ttk.Label(controls, text="Search folder").grid(row=0, column=0, sticky="w", padx=(0, 12), pady=(0, 8))
        ttk.Entry(controls, textvariable=self.history_root_var).grid(row=0, column=1, sticky="ew", pady=(0, 8))
        ttk.Button(controls, text="Refresh", command=lambda: self.show_view("history")).grid(row=0, column=2, sticky="e", padx=(12, 0), pady=(0, 8))

        selection = self.build_history_selection()
        if not selection.items:
            ttk.Label(
                frame,
                text=(
                    f"No run_summary.json files were found under {selection.search_root}. "
                    "Finish one run with the online or offline wizard, then refresh."
                ),
                wraplength=620,
                justify="left",
            ).grid(row=3, column=0, sticky="w")
            return

        results = ttk.LabelFrame(frame, text="Recent runs", padding=16)
        results.grid(row=3, column=0, sticky="nsew", pady=(12, 0))
        results.columnconfigure(0, weight=1)
        frame.rowconfigure(3, weight=1)

        for idx, (_folder, label, details) in enumerate(selection.items):
            ttk.Label(results, text=label, font=("TkDefaultFont", 10, "bold")).grid(row=idx * 2, column=0, sticky="w")
            ttk.Label(results, text=details, wraplength=620, justify="left").grid(row=idx * 2 + 1, column=0, sticky="w", pady=(0, 8))

        guide = ttk.LabelFrame(frame, text="Selected guide", padding=16)
        guide.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        guide.columnconfigure(0, weight=1)
        summary_text = selection.selected_summary or "No summary selected."
        ttk.Label(guide, text=f"Summary: {summary_text}", wraplength=620, justify="left").grid(row=0, column=0, sticky="w")
        ttk.Label(guide, text=selection.selected_guide or "", wraplength=620, justify="left").grid(row=1, column=0, sticky="w", pady=(8, 0))

    def _add_readonly_row(self, parent, row: int, label: str, variable) -> None:
        ttk = self._ttk
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=4)
        entry = ttk.Entry(parent, textvariable=variable)
        entry.state(["readonly"])
        entry.grid(row=row, column=1, sticky="ew", pady=4)

    def _add_entry_row(self, parent, row: int, label: str, variable) -> None:
        ttk = self._ttk
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=4)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=4)

    def _build_sweep(self) -> SweepSpec:
        return SweepSpec(
            sample_rate=self.state.sample_rate,
            duration_s=self.state.duration_s,
            f_start=self.state.f_start_hz,
            f_end=self.state.f_end_hz,
            pre_silence_s=self.state.pre_silence_s,
            post_silence_s=self.state.post_silence_s,
            amplitude=self.state.amplitude,
        )

    def _parse_positive_int(self, raw: str, label: str) -> int:
        try:
            value = int(raw)
        except ValueError as exc:
            raise ValueError(f"{label} must be a whole number.") from exc
        if value <= 0:
            raise ValueError(f"{label} must be greater than 0.")
        return value

    def start_online_measurement(self) -> None:
        output_dir = self.output_dir_var.get().strip()
        if not output_dir:
            raise ValueError("Output folder is required.")
        iterations = self._parse_positive_int(self.iterations_var.get().strip(), "Iterations")
        max_filters = self._parse_positive_int(self.max_filters_var.get().strip(), "Max PEQ filters")
        target_csv = self.target_csv_var.get().strip() or None
        output_target = self.output_target_var.get().strip() or None
        input_target = self.input_target_var.get().strip() or None

        self._run_background_task(
            task_name="measure-online",
            progress_title="Running online measurement",
            progress_body=f"Working in {output_dir}. The GUI is running the shared online pipeline now: playback, record, analyze, fit, and export.",
            worker=lambda: self._online_runner(
                output_dir=output_dir,
                sweep_spec=self._build_sweep(),
                target_path=target_csv,
                output_target=output_target,
                input_target=input_target,
                iterations=iterations,
                max_filters=max_filters,
            ),
            on_success=lambda _result: self._set_completion(
                title="Online measurement complete",
                summary=f"The guided online run finished in {output_dir}.",
                steps=(
                    f"Review outputs in {output_dir}.",
                    "Start with run_summary.json, then use equalizer_apo.txt or camilladsp_full.yaml.",
                    "If the wrong devices were used, rerun with clearer playback/capture target matches.",
                ),
            ),
        )

    def start_offline_prepare(self) -> None:
        output_dir = self.output_dir_var.get().strip()
        if not output_dir:
            raise ValueError("Package folder is required.")
        out_dir = Path(output_dir)
        notes = self.offline_notes_var.get().strip()
        self._run_background_task(
            task_name="prepare-offline",
            progress_title="Writing offline sweep package",
            progress_body=f"Preparing sweep.wav and measurement_plan.json in {out_dir}.",
            worker=lambda: self._offline_prepare_runner(
                self._build_sweep(),
                OfflineMeasurementPlan(sweep_wav=out_dir / "sweep.wav", metadata_json=out_dir / "measurement_plan.json", notes=notes),
            ),
            on_success=lambda _result: self._set_completion(
                title="Offline package ready",
                summary=f"The recorder-first package was written to {out_dir}.",
                steps=(
                    f"Play and record {out_dir / 'sweep.wav'} with your handheld recorder.",
                    "Keep the full capture, including extra tail, and do not trim the WAV before fitting.",
                    f"Then return here and run the offline fit into {self.offline_fit_output_var.get().strip() or (out_dir / 'fit')}",
                ),
            ),
        )

    def start_offline_fit(self) -> None:
        recording = self.offline_recording_var.get().strip()
        if not recording:
            raise ValueError("Recorded WAV is required.")
        out_dir = self.offline_fit_output_var.get().strip()
        if not out_dir:
            raise ValueError("Fit output folder is required.")
        max_filters = self._parse_positive_int(self.max_filters_var.get().strip(), "Max PEQ filters")
        target_csv = self.target_csv_var.get().strip() or None
        self._run_background_task(
            task_name="fit-offline",
            progress_title="Fitting imported offline recording",
            progress_body=f"Analyzing {recording} and exporting EQ outputs into {out_dir}.",
            worker=lambda: self._offline_fit_runner(recording, out_dir, self._build_sweep(), target_path=target_csv, max_filters=max_filters),
            on_success=lambda _result: self._set_completion(
                title="Offline fit complete",
                summary=f"The imported recording was analyzed and fitted into {out_dir}.",
                steps=(
                    f"Review outputs in {out_dir}.",
                    "Start with run_summary.json, then use equalizer_apo.txt or camilladsp_full.yaml.",
                    "If the fit looks wrong, re-record without trimming and try again.",
                ),
            ),
        )

    def _run_background_task(self, *, task_name: str, progress_title: str, progress_body: str, worker: Callable[[], object], on_success: Callable[[object], None]) -> None:
        if self._active_task_name is not None:
            raise RuntimeError("Another workflow is already running.")
        self._active_task_name = task_name
        self.progress_title_var.set(progress_title)
        self.progress_body_var.set(progress_body)
        self.show_view_progress()

        def target() -> None:
            try:
                result = worker()
            except Exception as exc:  # pragma: no cover
                self._task_queue.put(("error", exc))
                return
            self._task_queue.put(("success", (on_success, result)))

        threading.Thread(target=target, daemon=True).start()
        self._schedule_task_poll()

    def show_view_progress(self) -> None:
        for child in self.content.winfo_children():
            child.destroy()
        self._render_progress()

    def _schedule_task_poll(self) -> None:
        if hasattr(self.root, "after"):
            self.root.after(100, self._poll_task_queue)
        else:
            self._poll_task_queue()

    def _poll_task_queue(self) -> None:
        try:
            event, payload = self._task_queue.get_nowait()
        except queue.Empty:
            if self._active_task_name is not None and hasattr(self.root, "after"):
                self.root.after(100, self._poll_task_queue)
            return

        self._active_task_name = None
        if event == "error":
            exc = payload
            self._set_completion(
                title="Workflow could not finish",
                summary=str(exc),
                steps=(
                    "Check the paths and device targets shown in the wizard.",
                    "If this was an online run, confirm PipeWire playback and capture work from the terminal too.",
                ),
            )
            return
        on_success, result = payload
        on_success(result)

    def _set_completion(self, *, title: str, summary: str, steps: tuple[str, ...]) -> None:
        self._last_completion_steps = steps
        self.completion_title_var.set(title)
        self.completion_body_var.set(summary)
        for child in self.content.winfo_children():
            child.destroy()
        self._render_completion()


def create_app(
    root=None,
    *,
    config_path: str | Path | None = None,
    config_loader: ConfigLoader = load_or_create_config,
    online_runner: OnlineRunner = iterative_measure_and_fit,
    offline_prepare_runner: OfflinePrepareRunner = prepare_offline_measurement,
    offline_fit_runner: OfflineFitRunner = process_single_measurement,
):
    if root is None:
        import tkinter as tk

        root = tk.Tk()
    state = load_gui_state(config_path, config_loader=config_loader)
    return HeadMatchGuiApp(
        root,
        state,
        online_runner=online_runner,
        offline_prepare_runner=offline_prepare_runner,
        offline_fit_runner=offline_fit_runner,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="headmatch-gui", description="Launch the HeadMatch desktop shell.")
    parser.add_argument(
        "--config",
        default=None,
        help="Optional path to a JSON config file. Default: ~/.config/headmatch/config.json or $XDG_CONFIG_HOME/headmatch/config.json.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        app = create_app(config_path=args.config)
    except Exception as exc:
        if exc.__class__.__name__ == "TclError":
            raise SystemExit(f"GUI could not start: {exc}") from exc
        raise
    app.root.mainloop()
