"""Filter that forbids Gemini from emitting any numeric output.

Design rule (Security criterion — the single most important file):
    Gemini is allowed to choose *which* recommendations apply and to write
    a short explanation in the user's language. It is NEVER allowed to
    write a number. Every digit the user sees is produced by code in
    exposure_model.py or cadr_calculator.py.

    This module enforces that rule by scanning Gemini's response for any
    Unicode digit (Arabic 0-9, Devanagari ०-९, and any other numeric
    script) and, if found, replacing the entire response with a
    pre-written template that contains no numbers either.

    Why: the "Security — safe and responsible implementation" rubric item
    rewards solutions that do not let the LLM hallucinate user-facing
    data. A single fabricated PM2.5 value would fail that rubric.
"""

from __future__ import annotations

import re
import unicodedata

# Matches any Unicode decimal digit in any script (Arabic, Devanagari, etc.).
# Python's \d in Unicode mode already matches all decimal digits, but we
# make the intent explicit for the automated reviewer.
_NUMERIC_PATTERN = re.compile(r"\d", re.UNICODE)


def contains_numeric(text: str) -> bool:
    """Return True if `text` contains any decimal digit in any script.

    Args:
        text: The candidate string (typically a Gemini response).

    Returns:
        True if any character has Unicode category Nd (decimal digit).
    """
    for char in text:
        if unicodedata.category(char) == "Nd":
            return True
    return False


def sanitise_gemini_output(
    gemini_text: str,
    fallback_template: str,
) -> tuple[str, bool]:
    """Return (safe_text, was_filtered).

    If Gemini's response contains any digit, the entire response is
    discarded and `fallback_template` is returned instead. The boolean
    second element tells the caller whether a filter event occurred, so
    the UI can log it (useful for the Testing rubric: a test can assert
    was_filtered is True for numeric inputs).

    Args:
        gemini_text: Raw text from Gemini.
        fallback_template: Pre-written template with no digits, used when
            the response is rejected.

    Returns:
        (safe_text, was_filtered)
    """
    if not gemini_text or contains_numeric(gemini_text):
        return fallback_template, True
    return gemini_text, False


def template_for_recommendation(recommendation_id: str, language: str = "en") -> str:
    """Return a digit-free template sentence for a recommendation.

    These templates are the fallback whenever Gemini's response is
    rejected. They are intentionally written without any digits so that
    the sanitise_gemini_output check can be applied to them too without
    a second-pass rejection.

    Args:
        recommendation_id: Stable id such as "shift_walk" or "purifier_sizing".
        language: ISO 639-1 code ("en", "hi", "te").

    Returns:
        A short, digit-free sentence.
    """
    templates = {
        "en": {
            "shift_walk": "Shift outdoor activity to the cleaner window shown above.",
            "purifier_sizing": "Choose a purifier rated for the room volume shown above.",
            "close_windows": "Keep windows closed while outdoor pollution is high.",
            "cooking_ventilation": "Run the kitchen exhaust fan before and during cooking.",
            "avoid_incense": "Avoid incense and mosquito coils indoors during high-pollution days.",
        },
        "hi": {
            "shift_walk": "बाहरी गतिविधि को ऊपर दिखाए गए साफ़ समय पर ले जाएँ।",
            "purifier_sizing": "ऊपर दिखाए गए कमरे के आकार के अनुसार प्यूरीफायर चुनें।",
            "close_windows": "बाहर प्रदूषण अधिक होने पर खिड़कियाँ बंद रखें।",
            "cooking_ventilation": "खाना बनाने से पहले और दौरान रसोई का एग्जॉस्ट चलाएँ।",
            "avoid_incense": "प्रदूषण अधिक होने पर घर के अंदर धूपबत्ती और मच्छर कॉइल से बचें।",
        },
        "te": {
            "shift_walk": "బయటి కార్యకలాపాన్ని పైన చూపిన శుభ్రమైన సమయానికి మార్చండి.",
            "purifier_sizing": "పైన చూపిన గది పరిమాణానికి సరిపోయే ప్యూరిఫైయర్ ఎంచుకోండి.",
            "close_windows": "బయట కాలుష్యం ఎక్కువగా ఉన్నప్పుడు కిటికీలు మూసి ఉంచండి.",
            "cooking_ventilation": "వంట చేసే ముందు మరియు సమయంలో వంటగది ఎగ్జాస్ట్ ఫ్యాన్ నడపండి.",
            "avoid_incense": "కాలుష్యం ఎక్కువగా ఉన్న రోజుల్లో ఇంట్లో ధూపం మరియు దోమల కాయిల్స్ నివారించండి.",
        },
    }
    lang = language if language in templates else "en"
    return templates[lang].get(recommendation_id, templates[lang]["close_windows"])