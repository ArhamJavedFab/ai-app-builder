# ============================================================
# config.py — Central configuration for Planning Engine
# ============================================================

import os
from pathlib import Path


def _load_dotenv() -> None:
    """Load simple KEY=VALUE pairs from planning_engine/.env if present."""
    env_path = Path(__file__).with_name(".env")
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


_load_dotenv()

# ── Gemini ───────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_HERE")

# Planning uses Flash for speed on simple agents,
# Pro for reasoning-heavy agents (architecture, validation).
# Override these in .env if your Gemini account has different model access.
GEMINI_MODEL_FAST   = os.getenv("GEMINI_MODEL_FAST", "gemini-2.5-flash")
GEMINI_MODEL_PRO    = os.getenv("GEMINI_MODEL_PRO", "gemini-2.5-pro")

GEMINI_TEMPERATURE  = float(os.getenv("GEMINI_TEMPERATURE", "0.3"))
GEMINI_MAX_TOKENS   = int(os.getenv("GEMINI_MAX_TOKENS", "16384"))
GEMINI_JSON_RETRIES = int(os.getenv("GEMINI_JSON_RETRIES", "1"))

# ── Pipeline ─────────────────────────────────────────────────
# How many clarification questions to ask the user max
MAX_CLARIFICATION_QUESTIONS = 5
MAX_CLARIFICATION_ROUNDS = int(os.getenv("MAX_CLARIFICATION_ROUNDS", "2"))
MIN_REQUIREMENT_COMPLETENESS = float(os.getenv("MIN_REQUIREMENT_COMPLETENESS", "0.75"))

# Minimum confidence score (0–1) from intent analyzer
# below this threshold → force clarification round
MIN_INTENT_CONFIDENCE = 0.65
MAX_VALIDATION_REPAIR_ATTEMPTS = int(os.getenv("MAX_VALIDATION_REPAIR_ATTEMPTS", "2"))

# ── Cost tracking ──────────────────────────────────────────────
COST_LOG_DIR = os.getenv("COST_LOG_DIR", "cast_calculation")
COST_LOG_FILENAME = os.getenv("COST_LOG_FILENAME", "llm_usage.json")
GEMINI_INPUT_COST_PER_1M = float(os.getenv("GEMINI_INPUT_COST_PER_1M", "0.30"))
GEMINI_OUTPUT_COST_PER_1M = float(os.getenv("GEMINI_OUTPUT_COST_PER_1M", "2.50"))

# ── Flutter Specifics ─────────────────────────────────────────
FLUTTER_STATE_OPTIONS       = ["riverpod", "bloc", "provider", "getx", "mobx"]
FLUTTER_ARCH_OPTIONS        = [
    "feature_first_clean_architecture",
    "layered_clean_architecture",
    "mvc",
    "mvvm",
]
FLUTTER_NETWORK_OPTIONS     = ["dio", "http", "chopper"]
FLUTTER_LOCAL_DB_OPTIONS    = ["isar", "hive", "sqflite", "drift"]
FLUTTER_NAV_OPTIONS         = ["go_router", "auto_route", "navigator_2"]

# ── Output ────────────────────────────────────────────────────
OUTPUT_DIR          = "outputs"
FINAL_PLAN_FILENAME = "master_plan.json"

# ── Logging ───────────────────────────────────────────────────
VERBOSE = True   # Set False to suppress step-by-step logs
