from __future__ import annotations

from .common import BODY_WRAP, DETAIL_WRAP, SECTION_PAD


def render_progress(ttk, frame, *, title: str, body: str) -> None:
    ttk.Label(frame, text=title, style="Title.TLabel").grid(row=0, column=0, sticky="w")
    ttk.Label(frame, text=body, wraplength=BODY_WRAP, justify="left").grid(row=1, column=0, sticky="w", pady=(8, 12))
    note = ttk.LabelFrame(frame, text="What to do now", padding=SECTION_PAD)
    note.grid(row=2, column=0, sticky="ew")
    ttk.Label(
        note,
        text="Keep this window open while the shared pipeline runs. This screen will switch to a completion summary when it finishes.",
        wraplength=DETAIL_WRAP,
        justify="left",
    ).grid(row=0, column=0, sticky="w")


def render_completion(ttk, frame, *, title: str, body: str, steps: tuple[str, ...], clipping_assessment=None, on_home, on_history) -> None:
    ttk.Label(frame, text=title, style="Title.TLabel").grid(row=0, column=0, sticky="w")
    ttk.Label(frame, text=body, wraplength=BODY_WRAP, justify="left").grid(row=1, column=0, sticky="w", pady=(8, 12))
    row = 2
    if clipping_assessment:
        card = ttk.LabelFrame(frame, text="EQ clipping assessment", padding=SECTION_PAD)
        card.grid(row=row, column=0, sticky="ew")
        card.columnconfigure(1, weight=1)
        indicator = "⚠" if clipping_assessment.get("will_clip") else "✓"
        status = "Clipping risk detected" if clipping_assessment.get("will_clip") else "No clipping risk detected"
        ttk.Label(card, text=f"{indicator} {status}", style="Heading.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(card, text="Preamp recommendation").grid(row=1, column=0, sticky="w", padx=(0, 12), pady=2)
        ttk.Label(card, text=f"{float(clipping_assessment.get('preamp_db', 0.0)):+.2f} dB").grid(row=1, column=1, sticky="w", pady=2)
        ttk.Label(card, text="Max boost level").grid(row=2, column=0, sticky="w", padx=(0, 12), pady=2)
        ttk.Label(card, text=f"{max(float(clipping_assessment.get('left_peak_boost_db', 0.0)), float(clipping_assessment.get('right_peak_boost_db', 0.0))):+.2f} dB").grid(row=2, column=1, sticky="w", pady=2)
        ttk.Label(card, text="Headroom loss").grid(row=3, column=0, sticky="w", padx=(0, 12), pady=2)
        ttk.Label(card, text=f"{float(clipping_assessment.get('headroom_loss_db', 0.0)):.2f} dB").grid(row=3, column=1, sticky="w", pady=2)
        warning = clipping_assessment.get("quality_concern")
        if warning:
            ttk.Label(card, text="Quality warning").grid(row=4, column=0, sticky="w", padx=(0, 12), pady=2)
            ttk.Label(card, text=warning, wraplength=DETAIL_WRAP, justify="left").grid(row=4, column=1, sticky="w", pady=2)
        row += 1
    card = ttk.LabelFrame(frame, text="Next steps", padding=SECTION_PAD)
    card.grid(row=row, column=0, sticky="ew")
    for idx, step in enumerate(steps):
        ttk.Label(card, text=f"- {step}", wraplength=DETAIL_WRAP, justify="left").grid(row=idx, column=0, sticky="w", pady=2)
    actions = ttk.Frame(frame, padding=(0, 12, 0, 0))
    actions.grid(row=row + 1, column=0, sticky="w")
    ttk.Button(actions, text="Back to Measure", command=on_home).grid(row=0, column=0, sticky="w")
    ttk.Button(actions, text="Open Results", command=on_history).grid(row=0, column=1, sticky="w", padx=(12, 0))


__all__ = ['render_completion', 'render_progress']
