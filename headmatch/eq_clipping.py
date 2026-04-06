"""EQ clipping prediction.

Predicts whether a fitted EQ profile will cause digital clipping when applied,
and computes appropriate preamp gains to prevent clipping.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np

from .peq import PEQBand, peq_chain_response_db


@dataclass(frozen=True)
class EQClippingAssessment:
    """Assessment of whether an EQ profile will cause clipping.
    
    When EQ filters have positive gain at some frequencies, applying them
    can push the signal above 0 dBFS, causing digital clipping. The standard
    mitigation is to apply a preamp (global negative gain) equal to the
    maximum positive boost.
    """
    
    left_peak_boost_db: float
    """Maximum positive boost in the left channel EQ curve (dB)."""
    
    right_peak_boost_db: float
    """Maximum positive boost in the right channel EQ curve (dB)."""
    
    left_preamp_db: float
    """Recommended preamp gain for left channel to prevent clipping (dB, <= 0)."""
    
    right_preamp_db: float
    """Recommended preamp gain for right channel to prevent clipping (dB, <= 0)."""
    
    total_preamp_db: float
    """Overall preamp needed (max of left and right) (dB, <= 0)."""
    
    will_clip: bool
    """True if EQ profile has any positive boost that could cause clipping."""
    
    headroom_loss_db: float
    """How much signal-to-noise ratio is lost due to preamp reduction (dB)."""
    
    quality_concern: str | None
    """Human-readable concern message if preamp reduction is severe."""


def assess_eq_clipping(
    freqs_hz: np.ndarray,
    sample_rate: int,
    left_bands: List[PEQBand],
    right_bands: List[PEQBand],
) -> EQClippingAssessment:
    """Assess whether an EQ profile will cause clipping.
    
    Args:
        freqs_hz: Frequency array for computing EQ response.
        sample_rate: Sample rate for computing EQ response.
        left_bands: PEQ bands for left channel.
        right_bands: PEQ bands for right channel.
    
    Returns:
        EQClippingAssessment with clipping prediction and preamp recommendations.
    """
    # Compute EQ response curves
    left_eq_db = peq_chain_response_db(freqs_hz, sample_rate, left_bands)
    right_eq_db = peq_chain_response_db(freqs_hz, sample_rate, right_bands)
    
    # Find peak positive boost (this is what would cause clipping)
    left_peak_db = float(np.max(left_eq_db))
    right_peak_db = float(np.max(right_eq_db))
    
    # Preamp needed is negative of the peak boost
    # (adding -6 dB preamp for a +6 dB peak keeps signal below 0 dBFS)
    left_preamp = -left_peak_db
    right_preamp = -right_peak_db
    total_preamp = min(left_preamp, right_preamp)  # More negative = more reduction needed
    
    # Will clip if any positive boost exists
    will_clip = left_peak_db > 0 or right_peak_db > 0
    
    # Headroom loss is the amount of signal reduction (preamp applied)
    headroom_loss = max(left_peak_db, right_peak_db)
    
    # Quality concern if preamp is very negative (more than 6 dB loss)
    quality_concern = None
    if headroom_loss > 12:
        quality_concern = (
            f"Severe headroom loss ({headroom_loss:.1f} dB). Consider using fewer filters "
            "or lower gains to maintain signal quality."
        )
    elif headroom_loss > 6:
        quality_concern = (
            f"Moderate headroom loss ({headroom_loss:.1f} dB). EQ pushes may reduce "
            "signal-to-noise ratio when compensated with preamp."
        )
    
    return EQClippingAssessment(
        left_peak_boost_db=left_peak_db,
        right_peak_boost_db=right_peak_db,
        left_preamp_db=left_preamp,
        right_preamp_db=right_preamp,
        total_preamp_db=total_preamp,
        will_clip=will_clip,
        headroom_loss_db=headroom_loss,
        quality_concern=quality_concern,
    )


def format_clipping_assessment(assessment: EQClippingAssessment) -> str:
    """Format a human-readable clipping assessment summary.
    
    Args:
        assessment: EQ clipping assessment result.
    
    Returns:
        Multi-line summary string for CLI output.
    """
    lines = [
        "EQ Clipping Assessment:",
        f"  Left peak boost:  {assessment.left_peak_boost_db:+.1f} dB",
        f"  Right peak boost: {assessment.right_peak_boost_db:+.1f} dB",
        f"  Preamp needed:     {assessment.total_preamp_db:.1f} dB",
    ]
    
    if assessment.will_clip:
        lines.insert(1, "  ⚠️  Positive boost detected — preamp required to prevent clipping.")
    else:
        lines.insert(1, "  ✓ No positive boost — no preamp needed.")
    
    if assessment.quality_concern:
        lines.append(f"  Note: {assessment.quality_concern}")
    
    return "\n".join(lines)


def format_clipping_summary(assessment: EQClippingAssessment) -> str:
    """Format a concise one-line summary for logging.
    
    Args:
        assessment: EQ clipping assessment result.
    
    Returns:
        One-line summary string.
    """
    if assessment.will_clip:
        return f"EQ clipping: preamp {assessment.total_preamp_db:.1f} dB needed (peak boost {max(assessment.left_peak_boost_db, assessment.right_peak_boost_db):.1f} dB)"
    return "EQ clipping: OK (no positive boost)"
