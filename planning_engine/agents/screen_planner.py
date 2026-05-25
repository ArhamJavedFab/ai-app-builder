# ============================================================
# agents/screen_planner.py
# ============================================================

import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.gemini_client import call_gemini_json
from core.navigation_contract import rewrite_root_route_to_home
from core.prompt_loader import load_prompt_template
import config

SCREEN_PLANNER = load_prompt_template("screen_planner.md")

LOCAL_SCREEN_RULES = """
LOCAL-ONLY (data_tier is local_only):
- Set api_calls to "Local Storage: <action>" (e.g. "Local Storage: read all alarms") — NOT Firestore or Firebase.
- Do NOT add LoginScreen unless needs_auth is true.
"""


def plan_screens(intent: dict, features: dict) -> dict:
    """
    Stage 4 — Convert features into a full Flutter screen list.
    Returns {screens, reusable_components}.
    """
    if config.VERBOSE:
        print("  📱  Planning screens...")

    prompt = SCREEN_PLANNER.format(
        intent_json=json.dumps(intent, indent=2),
        features_json=json.dumps(features, indent=2),
    )
    if intent.get("data_tier") == "local_only":
        prompt = f"{prompt}\n\n{LOCAL_SCREEN_RULES}"
    result = call_gemini_json(prompt, use_pro=False)
    screens = result.get("screens", [])
    if isinstance(screens, list):
        rewrite_root_route_to_home([s for s in screens if isinstance(s, dict)])

    if config.VERBOSE:
        screens    = len(result.get("screens", []))
        components = len(result.get("reusable_components", []))
        print(f"      {screens} screens | {components} reusable components")

    return result
