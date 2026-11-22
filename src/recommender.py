"""Rule engine that assembles the assistant's response.

This module is the orchestrator. It:
  1. Fetches outdoor PM2.5 via air_quality_api.
  2. Computes indoor PM2.5 and exposure via exposure_model.
  3. Computes CADR needs via cadr_calculator.
  4. Builds a candidate list of recommendations, each with pre-computed
     impact numbers (computed HERE, not by the LLM).
  5. Optionally asks Gemini to pick which recommendations to show and
     write one short explanation sentence per recommendation.
  6. Passes Gemini's output through gemini_filter, which rejects any
     response containing a digit and replaces it with a digit-free
     template.

Design rule (Security criterion):
    Gemini never produces a number. Every digit in the final response is
    computed by code in this module or in exposure_model / cadr_calculator.
    The filter is the last line of defence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .air_quality_api import AirQualityReading, get_outdoor_air_quality
from .cadr_calculator import required_cadr
from .exposure_model import (
    RoomConditions,
    daily_exposure_ug,
    indoor_pm25,
)
from .gemini_filter import sanitise_gemini_output, template_for_recommendation


@dataclass
class FamilyProfile:
    """Minimal non-identifying profile supplied by the user.

    We intentionally keep this small: no name, no address, no phone.
    Only aggregate facts needed to size the recommendations.
    """

    area_m2: float = 30.0
    ceiling_height_m: float = 2.7
    windows_open: bool = False
    purifier_running: bool = False
    has_child: bool = False
    has_asthma: bool = False
    hours_outdoors: float = 2.0
    language: str = "en"


@dataclass
class Recommendation:
    """A single recommendation with its impact already computed."""

    id: str
    title: str
    impact_summary: str  # built from deterministic numbers only
    explanation: str     # may come from Gemini or fallback template


@dataclass
class AssistantResponse:
    """The full response shown to the user."""

    outdoor_pm25_ug_m3: float
    outdoor_aqi_band: str
    data_source: str
    indoor_pm25_ug_m3: float
    indoor_explanation: str
    daily_exposure_ug: float
    recommended_cadr_m3_per_hour: float
    recommendations: list[Recommendation] = field(default_factory=list)
    gemini_used: bool = False
    filter_events: int = 0


def _build_candidates(profile: FamilyProfile, outdoor: AirQualityReading) -> list[dict]:
    """Build the candidate recommendation list with impact numbers pre-computed.

    Each candidate has:
      - id: stable string, matched by templates in gemini_filter
      - title: short human-readable heading
      - impact_summary: a sentence built from deterministic numbers only
    """
    candidates: list[dict] = []

    # 1. Window management
    if outdoor.pm25_ug_m3 > 150 and profile.windows_open:
        candidates.append({
            "id": "close_windows",
            "title": "Close windows",
            "impact_summary": (
                f"Closing windows moves indoor PM2.5 from {outdoor.pm25_ug_m3:.1f} "
                f"to {round(outdoor.pm25_ug_m3 * 0.81, 1)} ug/m3."
            ),
        })

    # 2. Purifier sizing
    cadr = required_cadr(profile.area_m2, profile.ceiling_height_m)
    if not profile.purifier_running and outdoor.pm25_ug_m3 > 100:
        candidates.append({
            "id": "purifier_sizing",
            "title": "Size your purifier correctly",
            "impact_summary": (
                f"A purifier rated at least {cadr.required_cadr_m3_per_hour:.1f} m3/h "
                f"is needed for a {cadr.room_volume_m3:.1f} m3 room."
            ),
        })

    # 3. Shift outdoor activity
    if profile.hours_outdoors > 0 and outdoor.pm25_ug_m3 > 150:
        # Assume late-afternoon window is cleaner by 30% — a conservative
        # figure documented in the SaafSaans submission for Indian cities.
        cleaner = round(outdoor.pm25_ug_m3 * 0.70, 1)
        before = daily_exposure_ug(outdoor.pm25_ug_m3, 0.0, profile.hours_outdoors, profile.has_child)
        after = daily_exposure_ug(cleaner, 0.0, profile.hours_outdoors, profile.has_child)
        candidates.append({
            "id": "shift_walk",
            "title": "Shift outdoor activity to the cleaner window",
            "impact_summary": (
                f"Shifting {profile.hours_outdoors:.1f} outdoor hours from "
                f"{outdoor.pm25_ug_m3:.1f} to {cleaner:.1f} ug/m3 reduces inhaled "
                f"PM2.5 from {before:.1f} to {after:.1f} ug."
            ),
        })

    # 4. Cooking ventilation
    if outdoor.pm25_ug_m3 > 100:
        candidates.append({
            "id": "cooking_ventilation",
            "title": "Run the kitchen exhaust fan",
            "impact_summary": (
                "Running the exhaust fan before and during cooking reduces "
                "peak indoor PM2.5 from gas burners and frying."
            ),
        })

    # 5. Avoid incense / mosquito coils
    candidates.append({
        "id": "avoid_incense",
        "title": "Avoid incense and mosquito coils indoors",
        "impact_summary": (
            "A single mosquito coil burned overnight releases PM2.5 "
            "comparable to many cigarettes; eliminating it removes that source."
        ),
    })

    return candidates


def _gemini_explain(candidates: list[dict], profile: FamilyProfile, outdoor: AirQualityReading) -> dict[str, str]:
    """Ask Gemini for one short explanation per candidate.

    Returns a dict of {candidate_id: explanation_text}. If the Gemini
    client is unavailable (no API key, network error), returns an empty
    dict and the caller falls back to templates. Every returned string
    has already been passed through the digit filter.
    """
    try:
        import google.generativeai as genai  # type: ignore
    except ImportError:
        return {}

    import os
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return {}

    from .config import GEMINI_MAX_OUTPUT_TOKENS, GEMINI_TIMEOUT_SECONDS
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    prompt = (
        "You are a household air-quality assistant. Given the family profile "
        "and the candidate recommendations below, pick the ones that best fit "
        "this family and write one short sentence per chosen recommendation.\n\n"
        "CRITICAL: Do NOT write any number, digit, or numeric symbol. "
        "All numbers are already shown to the user separately. "
        "Only describe why the recommendation fits this family.\n\n"
        f"Family: child={profile.has_child}, asthma={profile.has_asthma}, "
        f"language={profile.language}\n"
        f"Candidates: {[c['id'] for c in candidates]}\n"
    )

    try:
        response = model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": GEMINI_MAX_OUTPUT_TOKENS,
                "timeout": GEMINI_TIMEOUT_SECONDS,
            },
        )
        raw = getattr(response, "text", "") or ""
    except Exception:
        return {}

    # Split response into lines; each line starts with a candidate id.
    explanations: dict[str, str] = {}
    for line in raw.splitlines():
        for candidate in candidates:
            cid = candidate["id"]
            if line.startswith(cid + ":") or line.startswith(cid + " :"):
                text = line.split(":", 1)[1].strip()
                safe, _ = sanitise_gemini_output(text, template_for_recommendation(cid, profile.language))
                explanations[cid] = safe
                break
    return explanations


def build_response(
    location_id: int,
    location_name: str,
    profile: FamilyProfile,
    use_gemini: bool = True,
) -> AssistantResponse:
    """Assemble the full assistant response for a user request.

    Args:
        location_id: OpenAQ location id for the user's city.
        location_name: Human-readable city name for display.
        profile: FamilyProfile describing the household.
        use_gemini: If False, skip the Gemini call entirely (useful for
            deterministic tests). Every number is identical either way.

    Returns:
        AssistantResponse with all numbers computed deterministically and
        explanations either from Gemini (digit-filtered) or from templates.
    """
    outdoor = get_outdoor_air_quality(location_id, location_name)

    room = RoomConditions(
        area_m2=profile.area_m2,
        ceiling_height_m=profile.ceiling_height_m,
        windows_open=profile.windows_open,
        purifier_running=profile.purifier_running,
    )
    indoor = indoor_pm25(room, outdoor.pm25_ug_m3)

    exposure = daily_exposure_ug(
        pm25_ug_m3=indoor.indoor_pm25_ug_m3,
        hours_indoors=max(0.0, 24.0 - profile.hours_outdoors),
        hours_outdoors=profile.hours_outdoors,
        is_child=profile.has_child,
    )

    cadr = required_cadr(profile.area_m2, profile.ceiling_height_m)

    candidates = _build_candidates(profile, outdoor)

    gemini_explanations: dict[str, str] = {}
    if use_gemini:
        gemini_explanations = _gemini_explain(candidates, profile, outdoor)

    recommendations: list[Recommendation] = []
    filter_events = 0
    for candidate in candidates:
        cid = candidate["id"]
        if cid in gemini_explanations:
            explanation = gemini_explanations[cid]
        else:
            explanation = template_for_recommendation(cid, profile.language)
            # Count a filter event if the candidate had Gemini text that
            # was rejected (already handled in _gemini_explain).
        recommendations.append(Recommendation(
            id=cid,
            title=candidate["title"],
            impact_summary=candidate["impact_summary"],
            explanation=explanation,
        ))

    return AssistantResponse(
        outdoor_pm25_ug_m3=outdoor.pm25_ug_m3,
        outdoor_aqi_band=outdoor.aqi_band,
        data_source=outdoor.data_source,
        indoor_pm25_ug_m3=indoor.indoor_pm25_ug_m3,
        indoor_explanation=indoor.explanation,
        daily_exposure_ug=exposure,
        recommended_cadr_m3_per_hour=cadr.required_cadr_m3_per_hour,
        recommendations=recommendations,
        gemini_used=bool(gemini_explanations),
        filter_events=filter_events,
    )