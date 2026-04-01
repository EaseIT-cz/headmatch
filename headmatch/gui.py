from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .app_identity import get_app_identity
from .contracts import FrontendConfig
from .settings import load_or_create_config


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


ConfigLoader = Callable[[str | Path | None], tuple[FrontendConfig, Path, bool]]


NAV_ITEMS: tuple[NavigationItem, ...] = (
    NavigationItem("home", "Home", "See the saved defaults and choose a workflow."),
    NavigationItem("measure-online", "Measure now", "Guided online measurement placeholder."),
    NavigationItem("prepare-offline", "Prepare offline", "Export the sweep package for recorder-first workflows."),
    NavigationItem("history", "History", "Navigation placeholder for the upcoming run browser."),
)


PLACEHOLDER_COPY = {
    "measure-online": (
        "This placeholder will become the guided online measurement wizard. "
        "For now it confirms navigation wiring and shows the defaults that will seed the wizard.",
        "Next up: wizard steps for playback, capture, progress, and completion.",
    ),
    "prepare-offline": (
        "This placeholder reserves the recorder-first workflow. "
        "It will later export the sweep package and hand off to offline fitting.",
        "Next up: notes, package export, and fit-offline handoff.",
    ),
    "history": (
        "Run browsing is intentionally not implemented in this task. "
        "This page keeps the shell structure ready for a later history browser.",
        "Next up: list recent runs and open the generated guides.",
    ),
}


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
    )


class HeadMatchGuiApp:
    def __init__(self, root, state: GuiState):
        import tkinter as tk
        from tkinter import ttk

        self.root = root
        self.state = state
        self._ttk = ttk
        self.current_view = tk.StringVar(master=root, value=state.current_view)
        self.output_dir_var = tk.StringVar(master=root, value=state.default_output_dir)
        self.target_csv_var = tk.StringVar(master=root, value=state.preferred_target_csv)
        self.output_target_var = tk.StringVar(master=root, value=state.pipewire_output_target)
        self.input_target_var = tk.StringVar(master=root, value=state.pipewire_input_target)
        self.iterations_var = tk.StringVar(master=root, value=str(state.start_iterations))
        self.max_filters_var = tk.StringVar(master=root, value=str(state.max_filters))
        self.history_root_var = tk.StringVar(master=root, value=str(Path(state.config_path).parent.parent))
        self.content = None

        self.root.title(f"HeadMatch {state.version_display}")

    def build_history_selection(self):
        from .history import build_history_selection

        return build_history_selection(self.history_root_var.get(), self.state.config_path.parent)

        self.root.minsize(920, 580)
        self._build_shell()
        self.show_view(state.current_view)

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
        ttk.Label(
            header,
            text="A guided desktop shell for headphone measurement, fitting, and future workflow screens.",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))

        nav = ttk.Frame(root, padding=(20, 8, 12, 20))
        nav.grid(row=1, column=0, sticky="nsw")
        ttk.Label(nav, text="Workflows", font=("TkDefaultFont", 11, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 8))
        for idx, item in enumerate(NAV_ITEMS, start=1):
            ttk.Button(nav, text=f"{item.label}\n{item.description}", command=lambda key=item.key: self.show_view(key), width=28).grid(
                row=idx,
                column=0,
                sticky="ew",
                pady=4,
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
        title = next(item.label for item in NAV_ITEMS if item.key == key)
        body, next_step = PLACEHOLDER_COPY[key]
        self._render_workflow_placeholder(title=title, body=body, primary_label=next_step)

    def _render_home(self) -> None:
        ttk = self._ttk
        frame = self.content
        ttk.Label(frame, text="Main screen", font=("TkDefaultFont", 15, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(
            frame,
            text=(
                "This is the GUI shell. It preloads your saved defaults and keeps the main workflows one click away. "
                "The measurement wizard itself is intentionally left as a placeholder in this task."
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

    def _render_workflow_placeholder(self, *, title: str, body: str, primary_label: str) -> None:
        ttk = self._ttk
        frame = self.content
        ttk.Label(frame, text=title, font=("TkDefaultFont", 15, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(frame, text=body, wraplength=620, justify="left").grid(row=1, column=0, sticky="w", pady=(8, 12))
        defaults = ttk.LabelFrame(frame, text="Preloaded values", padding=16)
        defaults.grid(row=2, column=0, sticky="ew")
        defaults.columnconfigure(1, weight=1)
        self._add_readonly_row(defaults, 0, "Output folder", self.output_dir_var)
        self._add_readonly_row(defaults, 1, "Playback target", self.output_target_var)
        self._add_readonly_row(defaults, 2, "Capture target", self.input_target_var)
        self._add_readonly_row(defaults, 3, "Target CSV", self.target_csv_var)
        ttk.Label(frame, text=primary_label, wraplength=620, justify="left").grid(row=3, column=0, sticky="w", pady=(12, 0))

    def _add_readonly_row(self, parent, row: int, label: str, variable) -> None:
        ttk = self._ttk
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=4)
        entry = ttk.Entry(parent, textvariable=variable)
        entry.state(["readonly"])
        entry.grid(row=row, column=1, sticky="ew", pady=4)



def create_app(root=None, *, config_path: str | Path | None = None, config_loader: ConfigLoader = load_or_create_config):
    if root is None:
        import tkinter as tk

        root = tk.Tk()
    state = load_gui_state(config_path, config_loader=config_loader)
    return HeadMatchGuiApp(root, state)



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
