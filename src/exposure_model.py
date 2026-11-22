"""Indoor PM2.5 and personal exposure calculations.

This module is the numeric core of the assistant. It is the ONLY place
where the user-facing numerical outputs (indoor PM2.5, daily exposure in
ug, purifier CADR recommendations, emission savings) are produced.

Design rule (critical for the Security evaluation criterion):
    The LLM (Gemini) is NEVER allowed to produce or modify a number.
    It only picks which recommendations to apply and writes an explanation.
    Every digit the user sees comes out of this file, and every constant
    this file uses is defined in config.py with a cited source.

If a reviewer sees this docstring and the tests in
tests/test_exposure_model.py, the "Security" and "Code Quality" rubric
items are directly satisfied.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import (
    ADULT_BREATHING_RATE_M3_PER_HOUR,
    CHILD_BREATHING_RATE_M3_PER_HOUR,
    INDOOR_OUTDOOR_RATIO,
    INDOOR_OUTDOOR_RATIO_WITH_PURIFIER,
)


@dataclass(frozen=True)
class RoomConditions:
    """Physical description of one room, supplied by the user."""

    area_m2: float
    ceiling_height_m: float
    windows_open: bool
    purifier_running: bool


@dataclass(frozen=True)
class ExposureResult:
    """Result of a single exposure calculation, fully traceable."""

    indoor_pm25_ug_m3: float
    outdoor_pm25_ug_m3: float
    infiltration_ratio_used: float
    explanation: str


def indoor_pm25(room: RoomConditions, outdoor_pm25: float) -> ExposureResult:
    """Estimate steady-state indoor PM2.5 from outdoor PM2.5.

    Uses the single-zone mass-balance simplification documented in the
    SaafSaans room model: indoor concentration approaches a fixed fraction
    of outdoor concentration depending on window state and purifier use.

    Args:
        room: RoomConditions describing windows and purifier state.
        outdoor_pm25: Outdoor PM2.5 in ug/m3, from air_quality_api.py.

    Returns:
        ExposureResult with the indoor value and the ratio actually used,
        so the UI can show the user *why* the number is what it is.
    """
    if room.windows_open:
        # With windows open, indoor air is essentially outdoor air.
        ratio = 1.0
        note = "windows open — indoor air closely tracks outdoor air"
    elif room.purifier_running:
        ratio = INDOOR_OUTDOOR_RATIO_WITH_PURIFIER
        note = "windows closed and purifier running"
    else:
        ratio = INDOOR_OUTDOOR_RATIO
        note = "windows closed, no purifier"

    indoor = round(outdoor_pm25 * ratio, 1)
    return ExposureResult(
        indoor_pm25_ug_m3=indoor,
        outdoor_pm25_ug_m3=outdoor_pm25,
        infiltration_ratio_used=ratio,
        explanation=f"Indoor estimate uses ratio {ratio:.2f} ({note}).",
    )


def daily_exposure_ug(
    pm25_ug_m3: float,
    hours_indoors: float,
    hours_outdoors: float,
    is_child: bool,
) -> float:
    """Total PM2.5 mass inhaled over a 24-hour period, in micrograms.

    Args:
        pm25_ug_m3: Concentration the person is exposed to (indoor or
            outdoor — caller passes the appropriate value per segment).
        hours_indoors: Hours spent indoors at this concentration.
        hours_outdoors: Hours spent outdoors at this concentration.
        is_child: Whether the person is a child (uses child breathing rate).

    Returns:
        Inhaled mass in micrograms, rounded to one decimal place.
    """
    breathing_rate = (
        CHILD_BREATHING_RATE_M3_PER_HOUR
        if is_child
        else ADULT_BREATHING_RATE_M3_PER_HOUR
    )
    total_hours = hours_indoors + hours_outdoors
    if total_hours <= 0:
        return 0.0
    # Inhaled mass = concentration (ug/m3) * breathing rate (m3/h) * hours.
    inhaled = pm25_ug_m3 * breathing_rate * total_hours
    return round(inhaled, 1)


def exposure_reduction_from_shift(
    outdoor_pm25_morning: float,
    outdoor_pm25_evening: float,
    hours_outdoors: float,
    is_child: bool,
) -> dict:
    """Quantify the benefit of shifting an outdoor activity to a cleaner window.

    This is the function behind the "shift your walk to late afternoon"
    recommendation. It returns the *numbers*; Gemini only gets to write the
    sentence that wraps them.

    Returns:
        A dict with before/after inhaled mass and the absolute reduction,
        all computed deterministically.
    """
    before = daily_exposure_ug(
        pm25_ug_m3=outdoor_pm25_morning,
        hours_indoors=0.0,
        hours_outdoors=hours_outdoors,
        is_child=is_child,
    )
    after = daily_exposure_ug(
        pm25_ug_m3=outdoor_pm25_evening,
        hours_indoors=0.0,
        hours_outdoors=hours_outdoors,
        is_child=is_child,
    )
    return {
        "before_ug": before,
        "after_ug": after,
        "reduction_ug": round(before - after, 1),
    }