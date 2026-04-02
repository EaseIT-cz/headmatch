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


def test_clone_target_matches_across_mixed_curve_source_shapes(tmp_path):
    source_measurement = tmp_path / 'source_measurement.csv'
    target_published = tmp_path / 'target_published.csv'
    source_measurement.write_text(
        'frequency_hz,response_db\n'
        '20,7\n'
        '100,3\n'
        '1000,1\n'
        '5000,0\n'
        '10000,-2\n'
        '20000,-4\n'
    )
    target_published.write_text(
        '# third-party export\n'
        'Freq (Hz),Amplitude (dB),Label\n'
        '20000,-1,air\n'
        '10000,1,treble\n'
        '5000,0,presence\n'
        '1000,3,anchor\n'
        '100,1,bass\n'
        '20,6,sub\n'
    )

    curve = clone_target_from_source_target(source_measurement, target_published)

    idx_20 = min(range(len(curve.freqs_hz)), key=lambda i: abs(curve.freqs_hz[i] - 20.0))
    idx_100 = min(range(len(curve.freqs_hz)), key=lambda i: abs(curve.freqs_hz[i] - 100.0))
    idx_10k = min(range(len(curve.freqs_hz)), key=lambda i: abs(curve.freqs_hz[i] - 10000.0))
    idx_20k = min(range(len(curve.freqs_hz)), key=lambda i: abs(curve.freqs_hz[i] - 20000.0))

    assert curve.values_db[idx_20] == pytest.approx(-3.0, abs=0.25)
    assert curve.values_db[idx_100] == pytest.approx(-4.0, abs=0.25)
    assert curve.values_db[idx_10k] == pytest.approx(1.0, abs=0.25)
    assert curve.values_db[idx_20k] == pytest.approx(1.0, abs=0.25)


def test_clone_target_round_trips_as_explicit_relative_target(tmp_path):
    src = tmp_path / 'source.csv'
    tgt = tmp_path / 'target.csv'
    out = tmp_path / 'clone.csv'
    src.write_text('frequency_hz,response_db\n20,1\n1000,0\n20000,-1\n')
    tgt.write_text('frequency_hz,response_db\n20,3\n1000,0\n20000,1\n')

    generated = clone_target_from_source_target(src, tgt, out)
    loaded = load_curve(out)

    assert generated.semantics == 'relative'
    assert loaded.semantics == 'relative'
    assert loaded.name == 'clone'
