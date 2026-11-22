"""Purifier CADR sizing.

Given a room's volume and a target clean-air turnover, this module
computes the minimum CADR (Clean Air Delivery Rate, in m3/h) a purifier
must have to meaningfully reduce indoor PM2.5.

Design rule (Security criterion):
    The user never sees a CADR number that was not computed here.
    Gemini only writes the sentence that wraps it.

Standard used:
    AHAM ANSI/AHAM AC-1 defines CADR as the volume of clean air delivered
    per unit time. A common rule of thumb is that CADR should be at least
    the room volume multiplied by 5 air changes per hour (ACH) for
    smoke/PM2.5 removal; we use 5 ACH and apply CADR_SAFETY_FACTOR to
    account for nominal-vs-real performance.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import CADR_SAFETY_FACTOR, CEILING_HEIGHT_M

# Air changes per hour needed for effective PM2.5 removal.
# Source: AHAM AC-1 guidance for smoke/PM2.5, commonly cited as 5 ACH.
TARGET_AIR_CHANGES_PER_HOUR = 5.0


@dataclass(frozen=True)
class CadrRecommendation:
    """Minimum CADR a purifier needs for this room, with the math shown."""

    room_volume_m3: float
    required_cadr_m3_per_hour: float
    explanation: str


def room_volume_m3(area_m2: float, ceiling_height_m: float = CEILING_HEIGHT_M) -> float:
    """Compute room volume in cubic metres.

    Args:
        area_m2: Floor area in square metres.
        ceiling_height_m: Ceiling height in metres; defaults to the Indian
            apartment standard defined in config.py.

    Returns:
        Volume in m3, rounded to one decimal place.
    """
    return round(area_m2 * ceiling_height_m, 1)


def required_cadr(area_m2: float, ceiling_height_m: float = CEILING_HEIGHT_M) -> CadrRecommendation:
    """Compute the minimum CADR for a room.

    Args:
        area_m2: Floor area in square metres.
        ceiling_height_m: Ceiling height in metres.

    Returns:
        CadrRecommendation with the required CADR in m3/h, adjusted upward
        by CADR_SAFETY_FACTOR so nominal marketing figures are not trusted.
    """
    volume = room_volume_m3(area_m2, ceiling_height_m)
    raw_cadr = volume * TARGET_AIR_CHANGES_PER_HOUR
    # Divide by safety factor because a purifier rated at nominal CADR
    # delivers less in practice (filter loading, fan curve, noise limits).
    adjusted = raw_cadr / CADR_SAFETY_FACTOR
    return CadrRecommendation(
        room_volume_m3=volume,
        required_cadr_m3_per_hour=round(adjusted, 1),
        explanation=(
            f"Room volume {volume} m3 × {TARGET_AIR_CHANGES_PER_HOUR:.0f} ACH "
            f"÷ {CADR_SAFETY_FACTOR:.2f} safety factor = "
            f"{adjusted:.1f} m3/h minimum CADR."
        ),
    )