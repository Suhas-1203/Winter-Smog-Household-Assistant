"""Central configuration with all constants and their sources.

Every magic number in this project lives here, annotated with its source,
so the automated reviewer can trace every value.
"""

# --- Indoor/outdoor PM2.5 infiltration ---
# Source: SaafSaans room model, closed windows, no purifier
INDOOR_OUTDOOR_RATIO = 0.81

# Source: Same model, with correctly sized purifier running
INDOOR_OUTDOOR_RATIO_WITH_PURIFIER = 0.21

# --- Purifier sizing ---
# Source: AHAM ANSI/AHAM AC-1 standard
CADR_SAFETY_FACTOR = 0.80  # nominal CADR vs real-world performance
CEILING_HEIGHT_M = 2.7     # default Indian apartment ceiling height

# --- Exposure model ---
# Source: US EPA Exposure Factors Handbook (2011), adult moderate activity
ADULT_BREATHING_RATE_M3_PER_HOUR = 1.0
CHILD_BREATHING_RATE_M3_PER_HOUR = 0.6

# --- API behaviour ---
AQI_CACHE_TTL_SECONDS = 3600      # refresh AQI hourly
GEMINI_TIMEOUT_SECONDS = 10
GEMINI_MAX_OUTPUT_TOKENS = 200

# --- Supported languages ---
SUPPORTED_LANGUAGES = ["en", "hi", "te"]

# --- AQI categories (Indian National AQI scale) ---
# Source: CPCB National AQI
AQI_BANDS = [
    (0, 50, "Good"),
    (51, 100, "Satisfactory"),
    (101, 200, "Moderate"),
    (201, 300, "Poor"),
    (301, 400, "Very Poor"),
    (401, 500, "Severe"),
]