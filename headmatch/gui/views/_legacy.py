from __future__ import annotations

from .common import (
    add_readonly_row,
    add_combobox_row,
    add_entry_row,
    add_picker_row,
    SECTION_PAD,
    FIELD_PAD_Y,
    BODY_WRAP,
    DETAIL_WRAP,
    COMPARISON_WRAP,
    ONLINE_STEPS,
    OFFLINE_STEPS,
    CLONE_TARGET_STEPS,
)
from .completion import render_progress, render_completion
from .online import render_online_wizard
from .setup import render_setup_check
from .offline import render_offline_wizard
from .basic import render_basic_mode, render_clone_target_workflow
from .history import (
    render_history_page,
    render_history_results,
    render_history,
    _confidence_badge,
    _confidence_display,
)
from .target_editor import (
    render_target_editor,
    _PlotGeometry,
    _plot_geometry,
    _render_curve_preview,
)
from .import_apo import render_import_apo
from .fetch_curve import render_fetch_curve


# Note: render_online_wizard is now implemented in .online and re-exported here for backward compatibility
# Note: render_setup_check is now implemented in .setup and re-exported here for backward compatibility
# Note: render_offline_wizard is now implemented in .offline and re-exported here for backward compatibility
# Note: render_progress and render_completion are now implemented in .completion and re-exported here for backward compatibility
# Note: render_basic_mode and render_clone_target_workflow are now implemented in .basic and re-exported here for backward compatibility
# Note: render_history_page, render_history_results, render_history are now implemented in .history and re-exported here for backward compatibility
# Note: render_target_editor, _PlotGeometry, _plot_geometry, _render_curve_preview are now implemented in .target_editor and re-exported here for backward compatibility
# Note: render_import_apo is now implemented in .import_apo and re-exported here for backward compatibility
# Note: render_fetch_curve is now implemented in .fetch_curve and re-exported here for backward compatibility


__all__ = [
    'BODY_WRAP',
    'CLONE_TARGET_STEPS',
    'COMPARISON_WRAP',
    'DETAIL_WRAP',
    'FIELD_PAD_Y',
    'OFFLINE_STEPS',
    'ONLINE_STEPS',
    'SECTION_PAD',
    '_PlotGeometry',
    '_confidence_badge',
    '_confidence_display',
    '_plot_geometry',
    '_render_curve_preview',
    'add_combobox_row',
    'add_entry_row',
    'add_picker_row',
    'add_readonly_row',
    'render_basic_mode',
    'render_clone_target_workflow',
    'render_completion',
    'render_fetch_curve',
    'render_history',
    'render_history_page',
    'render_history_results',
    'render_import_apo',
    'render_offline_wizard',
    'render_online_wizard',
    'render_progress',
    'render_setup_check',
    'render_target_editor',
]
