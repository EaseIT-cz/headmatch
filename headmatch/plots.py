from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np

from .analysis import MeasurementResult
from .peq import PEQBand, peq_chain_response_db
from .targets import TargetCurve, resample_curve


PLOT_Y_MIN = -18.0
PLOT_Y_MAX = 18.0


def _log_x_positions(freqs: np.ndarray, width: float, domain: np.ndarray | None = None) -> np.ndarray:
    source = domain if domain is not None else freqs
    log_min = np.log10(float(source[0]))
    log_max = np.log10(float(source[-1]))
    if np.isclose(log_max, log_min):
        return np.full_like(freqs, width * 0.5, dtype=np.float64)
    scale = width / (log_max - log_min)
    return (np.log10(freqs) - log_min) * scale


def _y_positions(values_db: np.ndarray, height: float) -> np.ndarray:
    clipped = np.clip(values_db, PLOT_Y_MIN, PLOT_Y_MAX)
    return (PLOT_Y_MAX - clipped) * (height / (PLOT_Y_MAX - PLOT_Y_MIN))


def _polyline_points(freqs: np.ndarray, values_db: np.ndarray, plot_x: float, plot_y: float, plot_w: float, plot_h: float) -> str:
    xs = _log_x_positions(freqs, plot_w) + plot_x
    ys = _y_positions(values_db, plot_h) + plot_y
    return ' '.join(f'{x:.2f},{y:.2f}' for x, y in zip(xs, ys))


def _svg_header(width: int, height: int, title: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<title>{escape(title)}</title>',
        '<style>',
        'text { font-family: Arial, sans-serif; fill: #111827; }',
        '.small { font-size: 12px; }',
        '.axis { stroke: #9ca3af; stroke-width: 1; }',
        '.grid { stroke: #d1d5db; stroke-width: 1; stroke-dasharray: 4 4; }',
        '.legend-line { stroke-width: 3; }',
        '</style>',
    ]


def _grid_lines(freqs: np.ndarray, plot_x: float, plot_y: float, plot_w: float, plot_h: float) -> list[str]:
    lines: list[str] = []
    for db in (-15, -10, -5, 0, 5, 10, 15):
        y = float(_y_positions(np.array([db]), plot_h)[0] + plot_y)
        klass = 'axis' if db == 0 else 'grid'
        lines.append(f'<line class="{klass}" x1="{plot_x:.2f}" y1="{y:.2f}" x2="{plot_x + plot_w:.2f}" y2="{y:.2f}" />')
        lines.append(f'<text class="small" x="{plot_x - 8:.2f}" y="{y + 4:.2f}" text-anchor="end">{db:g}</text>')

    for freq in (20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000):
        if freq < freqs[0] or freq > freqs[-1]:
            continue
        x = float(_log_x_positions(np.array([freq], dtype=np.float64), plot_w, domain=freqs)[0] + plot_x)
        lines.append(f'<line class="grid" x1="{x:.2f}" y1="{plot_y:.2f}" x2="{x:.2f}" y2="{plot_y + plot_h:.2f}" />')
        label = f'{int(freq / 1000)}k' if freq >= 1000 else str(int(freq))
        lines.append(f'<text class="small" x="{x:.2f}" y="{plot_y + plot_h + 18:.2f}" text-anchor="middle">{label}</text>')
    return lines


def _draw_panel(title: str, freqs: np.ndarray, series: list[tuple[str, np.ndarray, str, str]], x: float, y: float, w: float, h: float) -> list[str]:
    parts = [f'<text x="{x:.2f}" y="{y - 14:.2f}" font-size="16" font-weight="bold">{escape(title)}</text>']
    parts.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" fill="white" stroke="#9ca3af" />')
    parts.extend(_grid_lines(freqs, x, y, w, h))
    for label, values, color, dash in series:
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ''
        parts.append(
            f'<polyline fill="none" stroke="{color}" stroke-width="2.2"{dash_attr} points="{_polyline_points(freqs, values, x, y, w, h)}" />'
        )
    legend_x = x + 10
    legend_y = y + 20
    for idx, (label, _values, color, dash) in enumerate(series):
        yy = legend_y + idx * 18
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ''
        parts.append(f'<line class="legend-line" x1="{legend_x:.2f}" y1="{yy:.2f}" x2="{legend_x + 20:.2f}" y2="{yy:.2f}" stroke="{color}"{dash_attr} />')
        parts.append(f'<text class="small" x="{legend_x + 28:.2f}" y="{yy + 4:.2f}">{escape(label)}</text>')
    return parts


def _write_svg(path: Path, width: int, height: int, title: str, body: list[str]) -> None:
    lines = _svg_header(width, height, title)
    lines.extend(body)
    lines.append('</svg>')
    path.write_text('\n'.join(lines) + '\n', encoding="utf-8")


def render_fit_graphs(
    out_dir: str | Path,
    result: MeasurementResult,
    target: TargetCurve,
    sample_rate: int,
    left_bands: list[PEQBand],
    right_bands: list[PEQBand],
) -> dict[str, str]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    freqs = result.freqs_hz
    target_resampled = resample_curve(target, freqs)
    if target_resampled.semantics == 'relative':
        left_target_db = result.left_db + target_resampled.values_db
        right_target_db = result.right_db + target_resampled.values_db
    else:
        left_target_db = target_resampled.values_db
        right_target_db = target_resampled.values_db
    left_fitted = result.left_db + peq_chain_response_db(freqs, sample_rate, left_bands)
    right_fitted = result.right_db + peq_chain_response_db(freqs, sample_rate, right_bands)

    paths = {
        'overview': str(out_dir / 'fit_overview.svg'),
        'left': str(out_dir / 'fit_left.svg'),
        'right': str(out_dir / 'fit_right.svg'),
    }

    overview_body = [
        '<text x="40" y="34" font-size="20" font-weight="bold">HeadMatch fit overview</text>',
        '<text class="small" x="40" y="54">Raw vs smoothed measurement, target curve, and predicted fitted result.</text>',
    ]
    overview_body.extend(
        _draw_panel(
            'Left channel',
            freqs,
            [
                ('Left raw', result.left_raw_db, '#9ca3af', ''),
                ('Left measured', result.left_db, '#2563eb', ''),
                ('Left fitted', left_fitted, '#16a34a', ''),
                ('Target', left_target_db, '#dc2626', '8 6'),
            ],
            70,
            80,
            1030,
            250,
        )
    )
    overview_body.extend(
        _draw_panel(
            'Right channel',
            freqs,
            [
                ('Right raw', result.right_raw_db, '#9ca3af', ''),
                ('Right measured', result.right_db, '#7c3aed', ''),
                ('Right fitted', right_fitted, '#16a34a', ''),
                ('Target', right_target_db, '#dc2626', '8 6'),
            ],
            70,
            390,
            1030,
            250,
        )
    )
    _write_svg(Path(paths['overview']), 1180, 690, 'HeadMatch fit overview', overview_body)

    for side, measured, raw, fitted, side_target, color in (
        ('left', result.left_db, result.left_raw_db, left_fitted, left_target_db, '#2563eb'),
        ('right', result.right_db, result.right_raw_db, right_fitted, right_target_db, '#7c3aed'),
    ):
        body = [
            f'<text x="40" y="34" font-size="20" font-weight="bold">{side.capitalize()} channel fit</text>',
            '<text class="small" x="40" y="54">Raw vs smoothed measurement, target curve, and predicted fitted result.</text>',
        ]
        body.extend(
            _draw_panel(
                f'{side.capitalize()} channel',
                freqs,
                [
                    ('Raw', raw, '#9ca3af', ''),
                    ('Measured', measured, color, ''),
                    ('Fitted', fitted, '#16a34a', ''),
                    ('Target', side_target, '#dc2626', '8 6'),
                ],
                70,
                80,
                1030,
                250,
            )
        )
        _write_svg(Path(paths[side]), 1180, 390, f'HeadMatch {side} fit', body)

    return paths
