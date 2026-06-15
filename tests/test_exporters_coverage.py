"""Coverage tests for headmatch.exporters edge branches."""
from __future__ import annotations

import headmatch.exporters as exporters


class TestShelfSToQNonPositiveInner:
    def test_returns_default_q_when_inner_non_positive(self, monkeypatch):
        """_shelf_s_to_q returns 0.707 when the RBJ inner term is <= 0 (line 38).

        For all valid inputs ``s`` is clamped to [0.1, 1.0], which keeps
        ``(1/s - 1) >= 0`` and therefore ``inner >= 2`` — the guard is defensive.
        To exercise it deterministically we shadow the module-level ``min`` so the
        upper clamp is defeated, letting ``s`` exceed 1.0 (making ``1/s - 1`` < 0).
        With a large gain ``A`` grows enough that ``inner`` goes non-positive.
        """
        monkeypatch.setattr(exporters, "min", lambda *a, **k: 2.0, raising=False)
        result = exporters._shelf_s_to_q(2.0, 30.0)
        assert result == 0.707
