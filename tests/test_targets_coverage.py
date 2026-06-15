"""Coverage tests for targets.py error/edge branches."""
from __future__ import annotations

import numpy as np
import pytest

from headmatch.targets import (
    clone_target_from_source_target,
    load_curve,
    normalize_at_1khz,
)


class TestNormalizeAt1kHzGuards:
    def test_shape_mismatch_raises(self):
        # line 29
        freqs = np.array([20.0, 1000.0, 20000.0])
        values = np.array([0.0, 0.0])
        with pytest.raises(ValueError, match='same shape'):
            normalize_at_1khz(freqs, values)

    def test_too_few_points_raises(self):
        # line 31
        freqs = np.array([1000.0])
        values = np.array([0.0])
        with pytest.raises(ValueError, match='at least two'):
            normalize_at_1khz(freqs, values)


class TestReadTargetMetadataBlankLines:
    def test_blank_lines_before_header_are_skipped(self, tmp_path):
        # The blank-line `continue` in _read_target_metadata is line 46.
        csv = tmp_path / 'curve.csv'
        csv.write_text(
            '\n'
            '# headmatch_target_semantics=relative\n'
            '\n'
            'frequency_hz,target_db\n'
            '20,0\n'
            '1000,0\n'
            '20000,0\n',
            encoding='utf-8',
        )
        curve = load_curve(csv)
        assert curve.semantics == 'relative'


class TestCloneTargetGuards:
    def test_identical_source_and_target_raises(self, tmp_path):
        # line 91
        csv = tmp_path / 'same.csv'
        csv.write_text('frequency_hz,target_db\n20,0\n1000,0\n20000,0\n', encoding='utf-8')
        with pytest.raises(ValueError, match='must be different files'):
            clone_target_from_source_target(csv, csv, tmp_path / 'out.csv')
