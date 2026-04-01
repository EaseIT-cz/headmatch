from __future__ import annotations

from .contracts import ConfidenceSummary


def confidence_troubleshooting_steps(confidence: ConfidenceSummary) -> tuple[str, ...]:
    steps: list[str] = []

    def add(step: str) -> None:
        if step not in steps:
            steps.append(step)

    warning_blob = " ".join(confidence.warnings).lower()

    if confidence.label == 'low':
        add('Try one fresh rerun before keeping this EQ preset.')

    if 'alignment' in warning_blob or 'timing may be unreliable' in warning_blob:
        add('Keep the room quiet and start the sweep again without touching the headphones or microphones.')
    if 'echoes' in warning_blob or 'noise' in warning_blob or 'rougher than expected' in warning_blob:
        add('Reduce background noise, avoid movement, and keep the headphone seal steady during the sweep.')
    if 'left and right measurements differ' in warning_blob or 'seated consistently' in warning_blob:
        add('Re-seat the headphones and microphones carefully so both sides sit the same way before re-measuring.')
    if 'residual error' in warning_blob or 'miss the target' in warning_blob or 'check the graphs' in warning_blob:
        add('Open the fit graphs before using the preset, and rerun if the result still looks uneven.')

    return tuple(steps[:3])
