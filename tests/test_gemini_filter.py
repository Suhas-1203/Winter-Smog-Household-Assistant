"""Tests for the Gemini digit filter.

This is the Security evidence: it proves that any numeric output from
the LLM is rejected and replaced by a digit-free template.
"""

from src.gemini_filter import (
    contains_numeric,
    sanitise_gemini_output,
    template_for_recommendation,
)


def test_contains_numeric_arabic():
    assert contains_numeric("PM2.5 is 162") is True


def test_contains_numeric_devanagari():
    # Devanagari digit १ (one)
    assert contains_numeric("कमरा १ है") is True


def test_contains_numeric_clean_text():
    assert contains_numeric("Keep windows closed.") is False


def test_sanitise_rejects_numeric_response():
    """A response containing any digit must be discarded entirely."""
    safe, was_filtered = sanitise_gemini_output(
        "Your indoor PM2.5 is 162.0 ug/m3.",
        "Keep windows closed.",
    )
    assert was_filtered is True
    assert safe == "Keep windows closed."


def test_sanitise_passes_clean_response():
    """A digit-free response is passed through unchanged."""
    safe, was_filtered = sanitise_gemini_output(
        "Keep windows closed because outdoor pollution is high.",
        "Fallback text.",
    )
    assert was_filtered is False
    assert safe == "Keep windows closed because outdoor pollution is high."


def test_sanitise_rejects_empty_response():
    """An empty response is treated as a filter event."""
    safe, was_filtered = sanitise_gemini_output("", "Fallback text.")
    assert was_filtered is True
    assert safe == "Fallback text."


def test_templates_are_digit_free():
    """Every fallback template must itself contain no digits."""
    for lang in ("en", "hi", "te"):
        for rid in ("shift_walk", "purifier_sizing", "close_windows",
                    "cooking_ventilation", "avoid_incense"):
            text = template_for_recommendation(rid, lang)
            assert contains_numeric(text) is False, f"{lang}/{rid} contains a digit: {text}"


def test_templates_unknown_id_falls_back():
    """Unknown recommendation id returns a safe default, not KeyError."""
    text = template_for_recommendation("does_not_exist", "en")
    assert isinstance(text, str)
    assert len(text) > 0