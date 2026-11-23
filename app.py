"""Flask entrypoint for the winter-smog household assistant."""

from __future__ import annotations

import os
from typing import Any

from flask import Flask, Response, render_template, request
from dotenv import load_dotenv

from src.config import SUPPORTED_LANGUAGES
from src.recommender import FamilyProfile, build_response

load_dotenv()

app = Flask(__name__)

CITY_LOCATIONS: dict[str, int] = {
    "Delhi": 2178,
    "Mumbai": 2245,
    "Bengaluru": 2247,
    "Hyderabad": 2249,
    "Chennai": 2248,
    "Kolkata": 2250,
}


@app.route("/", methods=["GET", "POST"])
def index() -> str:
    """Render the form and, on POST, the computed response."""
    response: Any = None
    error: str | None = None
    form_values: dict[str, str] = {
        "city": "Delhi",
        "area_m2": "30",
        "ceiling_height_m": "2.7",
        "windows_open": "",
        "purifier_running": "",
        "has_child": "",
        "has_asthma": "",
        "hours_outdoors": "2",
        "language": "en",
    }

    if request.method == "POST":
        try:
            form_values = {k: request.form.get(k, "") for k in form_values}
            profile = FamilyProfile(
                area_m2=float(form_values["area_m2"] or 30),
                ceiling_height_m=float(form_values["ceiling_height_m"] or 2.7),
                windows_open=bool(form_values["windows_open"]),
                purifier_running=bool(form_values["purifier_running"]),
                has_child=bool(form_values["has_child"]),
                has_asthma=bool(form_values["has_asthma"]),
                hours_outdoors=float(form_values["hours_outdoors"] or 2),
                language=form_values["language"] if form_values["language"] in SUPPORTED_LANGUAGES else "en",
            )
            location_id = CITY_LOCATIONS.get(form_values["city"], 2178)
            response = build_response(location_id, form_values["city"], profile)
        except (ValueError, KeyError) as exc:
            error = f"Could not read your input: {exc}"

    return render_template(
        "index.html",
        cities=list(CITY_LOCATIONS.keys()),
        languages=SUPPORTED_LANGUAGES,
        form=form_values,
        response=response,
        error=error,
    )


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_ENV") == "development", port=5000)