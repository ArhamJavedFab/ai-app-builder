# ============================================================
# agents/screen_planner.py
# ============================================================

import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.gemini_client import call_gemini_json
from core.prompt_templates import SCREEN_PLANNER
import config


def plan_screens(intent: dict, features: dict) -> dict:
    """
    Stage 4 — Convert features into a full Flutter screen list.
    Returns {screens, reusable_components}.
    """
    if config.VERBOSE:
        print("  📱  Planning screens...")

    filled = SCREEN_PLANNER.format(
        intent_json=json.dumps(intent, indent=2),
        features_json=json.dumps(features, indent=2),
    )
    result = call_gemini_json(filled, use_pro=False)

    if config.VERBOSE:
        screens    = len(result.get("screens", []))
        components = len(result.get("reusable_components", []))
        print(f"      {screens} screens | {components} reusable components")

    return result
