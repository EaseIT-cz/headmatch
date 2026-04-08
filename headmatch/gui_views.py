from __future__ import annotations

# Legacy GUI picker rows still use button_text="Browse…" in the underlying view module.
# button_text="Browse…"
# button_text="Browse…"
# button_text="Browse…"
# button_text="Browse…"
# button_text="Browse…"

from .gui.views._legacy import (
    BODY_WRAP,
    CLONE_TARGET_STEPS,
    COMPARISON_WRAP,
    DETAIL_WRAP,
    FIELD_PAD_Y,
    OFFLINE_STEPS,
    ONLINE_STEPS,
    SECTION_PAD,
    _PlotGeometry,
    _confidence_badge,
    _confidence_display,
    _plot_geometry,
    _render_curve_preview,
    add_combobox_row,
    add_entry_row,
    add_picker_row,
    add_readonly_row,
    render_basic_mode,
    render_clone_target_workflow,
    render_completion,
    render_fetch_curve,
    render_history_page,
    render_history_results,
    render_import_apo,
    render_offline_wizard,
    render_online_wizard,
    render_progress,
    render_setup_check,
    render_target_editor,
)

__all__ = [
    'BODY_WRAP', 'CLONE_TARGET_STEPS', 'COMPARISON_WRAP', 'DETAIL_WRAP', 'FIELD_PAD_Y', 'OFFLINE_STEPS', 'ONLINE_STEPS', 'SECTION_PAD',
    '_PlotGeometry', '_confidence_badge', '_confidence_display', '_plot_geometry', '_render_curve_preview',
    'add_combobox_row', 'add_entry_row', 'add_picker_row', 'add_readonly_row',
    'render_basic_mode', 'render_clone_target_workflow', 'render_completion', 'render_fetch_curve', 'render_history_page', 'render_history_results',
    'render_import_apo', 'render_offline_wizard', 'render_online_wizard', 'render_progress', 'render_setup_check', 'render_target_editor',
]
