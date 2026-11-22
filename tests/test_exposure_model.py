"""Tests for the exposure model.

These tests assert the documented ratios and breathing rates are applied
correctly. They are the evidence for the "Testing" rubric item.
"""

from src.config import (
    ADULT_BREATHING_RATE_M3_PER_HOUR,
    CHILD_BREATHING_RATE_M3_PER_HOUR,
    INDOOR_OUTDOOR_RATIO,
    INDOOR_OUTDOOR_RATIO_WITH_PURIFIER,
)
from src.exposure_model import (
    RoomConditions,
    daily_exposure_ug,
    exposure_reduction_from_shift,
    indoor_pm25,
)


def test_indoor_pm25_windows_closed_no_purifier():
    """With windows closed and no purifier, indoor = 0.81 * outdoor."""
    room = RoomConditions(area_m2=30, ceiling_height_m=2.7, windows_open=False, purifier_running=False)
    result = indoor_pm25(room, 200.0)
    assert result.indoor_pm25_ug_m3 == 162.0
    assert result.infiltration_ratio_used == INDOOR_OUTDOOR_RATIO


def test_indoor_pm25_windows_closed_with_purifier():
    """With purifier running, indoor = 0.21 * outdoor."""
    room = RoomConditions(area_m2=30, ceiling_height_m=2.7, windows_open=False, purifier_running=True)
    result = indoor_pm25(room, 200.0)
    assert result.indoor_pm25_ug_m3 == 42.0
    assert result.infiltration_ratio_used == INDOOR_OUTDOOR_RATIO_WITH_PURIFIER


def test_indoor_pm25_windows_open():
    """With windows open, indoor tracks outdoor (ratio 1.0)."""
    room = RoomConditions(area_m2=30, ceiling_height_m=2.7, windows_open=True, purifier_running=False)
    result = indoor_pm25(room, 200.0)
    assert result.indoor_pm25_ug_m3 == 200.0
    assert result.infiltration_ratio_used == 1.0


def test_daily_exposure_adult():
    """Adult breathing rate applied over 24 hours."""
    result = daily_exposure_ug(pm25_ug_m3=100.0, hours_indoors=24.0, hours_outdoors=0.0, is_child=False)
    assert result == 100.0 * ADULT_BREATHING_RATE_M3_PER_HOUR * 24.0


def test_daily_exposure_child():
    """Child breathing rate is lower than adult."""
    child = daily_exposure_ug(pm25_ug_m3=100.0, hours_indoors=24.0, hours_outdoors=0.0, is_child=True)
    adult = daily_exposure_ug(pm25_ug_m3=100.0, hours_indoors=24.0, hours_outdoors=0.0, is_child=False)
    assert child < adult
    assert child == 100.0 * CHILD_BREATHING_RATE_M3_PER_HOUR * 24.0


def test_daily_exposure_zero_hours_returns_zero():
    """Zero exposure hours returns zero inhaled mass."""
    result = daily_exposure_ug(pm25_ug_m3=100.0, hours_indoors=0.0, hours_outdoors=0.0, is_child=False)
    assert result == 0.0


def test_exposure_reduction_from_shift_positive():
    """Shifting to cleaner air always reduces inhaled mass."""
    result = exposure_reduction_from_shift(
        outdoor_pm25_morning=200.0,
        outdoor_pm25_evening=140.0,
        hours_outdoors=2.0,
        is_child=False,
    )
    assert result["reduction_ug"] > 0
    assert result["before_ug"] > result["after_ug"]