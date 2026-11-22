"""Tests for the CADR calculator.

Verifies the room-volume math and the AHAM safety factor are applied
as documented in config.py.
"""

import pytest

from src.cadr_calculator import (
    TARGET_AIR_CHANGES_PER_HOUR,
    required_cadr,
    room_volume_m3,
)
from src.config import CADR_SAFETY_FACTOR, CEILING_HEIGHT_M


def test_room_volume_default_ceiling():
    """30 m2 * 2.7 m = 81.0 m3."""
    assert room_volume_m3(30.0) == 30.0 * CEILING_HEIGHT_M


def test_room_volume_custom_ceiling():
    """Custom ceiling height is respected."""
    assert room_volume_m3(20.0, 3.0) == 60.0


def test_required_cadr_math():
    """required CADR = volume * ACH / safety factor."""
    result = required_cadr(30.0)
    expected = round((30.0 * CEILING_HEIGHT_M * TARGET_AIR_CHANGES_PER_HOUR) / CADR_SAFETY_FACTOR, 1)
    assert result.required_cadr_m3_per_hour == expected


def test_required_cadr_increases_with_area():
    """Larger rooms require more CADR."""
    small = required_cadr(20.0).required_cadr_m3_per_hour
    large = required_cadr(50.0).required_cadr_m3_per_hour
    assert large > small


def test_required_cadr_explanation_contains_no_hallucination():
    """Explanation is built from computed values, not invented text."""
    result = required_cadr(30.0)
    assert "m3" in result.explanation
    assert "ACH" in result.explanation


def test_required_cadr_boundary_zero_area():
    """Zero-area room yields zero CADR."""
    result = required_cadr(0.0)
    assert result.required_cadr_m3_per_hour == 0.0


@pytest.mark.parametrize("area", [10.0, 25.0, 40.0, 100.0])
def test_required_cadr_monotonic(area):
    """CADR is monotonic in room area."""
    a = required_cadr(area).required_cadr_m3_per_hour
    b = required_cadr(area + 1.0).required_cadr_m3_per_hour
    assert b > a