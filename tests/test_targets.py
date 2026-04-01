from __future__ import annotations

import pytest

from headmatch.io_utils import load_fr_csv
from headmatch.targets import clone_target_from_source_target, load_curve


def test_load_fr_csv_accepts_common_column_variants_and_comments(tmp_path):
    csv_path = tmp_path / 'published_curve.csv'
    csv_path.write_text(
        '# published measurement export\n'
        'Freq (Hz),Amplitude (dB),Notes\n'
        '1000,3.0,anchor\n'
        '20,5.0,bass\n'
        '100,-1.0,mid\n'
    )

    freqs, vals = load_fr_csv(csv_path)

    assert freqs.tolist() == [20.0, 100.0, 1000.0]
    assert vals.tolist() == [5.0, -1.0, 3.0]


def test_load_curve_requires_1khz_coverage(tmp_path):
    csv_path = tmp_path / 'too_narrow.csv'
    csv_path.write_text('frequency_hz,response_db\n20,1\n500,2\n900,3\n')

    with pytest.raises(ValueError, match='1 kHz'):
        load_curve(csv_path)


def test_clone_target_rejects_overwriting_inputs(tmp_path):
    src = tmp_path / 'source.csv'
    tgt = tmp_path / 'target.csv'
    src.write_text('frequency_hz,response_db\n20,2\n1000,0\n20000,-1\n')
    tgt.write_text('frequency_hz,response_db\n20,4\n1000,1\n20000,-3\n')

    with pytest.raises(ValueError, match='Output CSV must not overwrite'):
        clone_target_from_source_target(src, tgt, src)


def test_clone_target_normalizes_each_curve_before_diff(tmp_path):
    src = tmp_path / 'source.csv'
    tgt = tmp_path / 'target.csv'
    out = tmp_path / 'clone.csv'
    src.write_text('frequency_hz,response_db\n20,6\n1000,1\n20000,-2\n')
    tgt.write_text('frequency_hz,response_db\n20,7\n1000,3\n20000,-1\n')

    curve = clone_target_from_source_target(src, tgt, out)

    idx = min(range(len(curve.freqs_hz)), key=lambda i: abs(curve.freqs_hz[i] - 1000.0))
    assert curve.values_db[idx] == pytest.approx(0.0, abs=1e-6)
    assert out.exists()
