import numpy as np
import pytest

from headmatch.peq import PEQBand, biquad_response_db, _edge_shelf_candidate




# --- TASK-081: Shelf parameter semantics tests ---

class TestShelfParameterSemantics:
    """Verify explicit slope vs legacy q-as-slope behavior for shelf bands."""

    def test_peaking_band_slope_is_none(self):
        band = PEQBand("peaking", 1000.0, -3.0, 1.5)
        assert band.slope is None
        assert band.q == 1.5

    def test_shelf_band_explicit_slope(self):
        band = PEQBand("lowshelf", 105.0, 3.0, 0.7, slope=0.7)
        assert band.slope == 0.7
        assert band.effective_slope == 0.7

    def test_shelf_band_legacy_q_as_slope(self):
        """Legacy: shelf with q=0.7 and no slope treats q as slope S."""
        band = PEQBand("lowshelf", 105.0, 3.0, 0.7)
        assert band.slope is None
        assert band.effective_slope == 0.7

    def test_shelf_explicit_slope_overrides_q(self):
        """When slope is set, it takes precedence over q for shelf evaluation."""
        band = PEQBand("highshelf", 8500.0, -2.0, 0.5, slope=0.8)
        assert band.effective_slope == 0.8

    def test_shelf_q_property_computes_from_slope(self):
        """shelf_q property converts slope S to true Q."""
        band = PEQBand("lowshelf", 105.0, 3.5, 0.7, slope=0.7)
        q = band.shelf_q
        assert isinstance(q, float)
        assert 0 < q < 10  # sanity

    def test_shelf_q_matches_exporter_conversion(self):
        """shelf_q should match the old _shelf_s_to_q function."""
        from headmatch.exporters import _shelf_s_to_q
        for s_val in [0.3, 0.5, 0.7, 1.0]:
            for gain in [-6.0, -3.0, 3.0, 6.0]:
                band = PEQBand("lowshelf", 105.0, gain, s_val, slope=s_val)
                expected = _shelf_s_to_q(s_val, gain)
                assert abs(band.shelf_q - expected) < 1e-3, (
                    f"s={s_val} gain={gain}: shelf_q={band.shelf_q} vs exporter={expected}"
                )

    def test_biquad_response_identical_with_explicit_slope(self):
        """Biquad evaluation should be identical whether slope is set explicitly or via legacy q."""
        import numpy as np
        freqs = np.geomspace(20, 20000, 200)
        sr = 48000
        legacy = PEQBand("lowshelf", 105.0, 4.0, 0.7)
        explicit = PEQBand("lowshelf", 105.0, 4.0, 0.7, slope=0.7)
        resp_legacy = biquad_response_db(freqs, sr, legacy)
        resp_explicit = biquad_response_db(freqs, sr, explicit)
        np.testing.assert_allclose(resp_legacy, resp_explicit, atol=1e-10)

    def test_edge_shelf_candidate_sets_slope(self):
        """_edge_shelf_candidate should set slope explicitly on created bands."""
        import numpy as np
        freqs = np.geomspace(20, 20000, 200)
        # Create a target with obvious low-frequency shelf need
        target = np.zeros_like(freqs)
        target[freqs < 140] = 5.0  # big boost below 140 Hz
        band = _edge_shelf_candidate(freqs, target, kind="lowshelf", max_gain_db=12.0)
        if band is not None:
            assert band.slope is not None, "Shelf candidate should have explicit slope"
            assert band.slope == band.q  # both set to same value
