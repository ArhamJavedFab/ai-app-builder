# ============================================================
# agents/feature_planner.py
# ============================================================

import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.gemini_client import call_gemini_json
from core.prompt_templates import FEATURE_PLANNER
import config


def plan_features(intent: dict, clarifications: dict) -> dict:
    """
    Stage 3 — Convert intent into a structured feature breakdown.
    Returns {features, mvp_features, post_mvp_features}.
    """
    if config.VERBOSE:
        print("  🧩  Planning features...")

    filled = FEATURE_PLANNER.format(
        intent_json=json.dumps(intent, indent=2),
        clarifications=json.dumps(clarifications, indent=2),
    )
    result = call_gemini_json(filled, use_pro=False)

    if config.VERBOSE:
        count = sum(len(m.get("items", [])) for m in result.get("features", []))
        modules = len(result.get("features", []))
        print(f"      {modules} modules | {count} total features")

    return result
