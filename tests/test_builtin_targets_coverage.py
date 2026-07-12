"""Coverage tests for builtin_targets.py."""
from __future__ import annotations

import pytest

from headmatch.builtin_targets import builtin_target_label, materialize_builtin_target
from headmatch.exceptions import ConfigError


def test_builtin_target_label_returns_display_name():
    # line 37
    assert builtin_target_label('harman') == 'Harman'
    assert builtin_target_label('flat') == 'Flat (default)'


def test_materialize_unknown_target_raises(tmp_path):
    # line 51
    with pytest.raises(ConfigError, match='unknown built-in target'):
        materialize_builtin_target('does_not_exist', tmp_path)
