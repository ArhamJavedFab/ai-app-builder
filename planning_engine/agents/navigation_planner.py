# ============================================================
# agents/navigation_planner.py
# ============================================================

import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.gemini_client import call_gemini_json
from core.navigation_contract import finalize_navigation
from core.prompt_loader import load_prompt_template
import config

NAVIGATION_PLANNER = load_prompt_template("navigation_planner.md")


def plan_navigation(intent: dict, screens: dict) -> dict:
    """
    Stage 5 — Design the complete go_router navigation map.
    Returns full navigation structure dict.
    """
    if config.VERBOSE:
        print("  🗺️   Planning navigation...")

    filled = NAVIGATION_PLANNER.format(
        intent_json=json.dumps(intent, indent=2),
        screens_json=json.dumps(screens, indent=2),
    )
    result = call_gemini_json(filled, use_pro=False)
    screens = screens.get("screens", []) if isinstance(screens, dict) else []
    result = finalize_navigation(
        [s for s in screens if isinstance(s, dict)],
        result if isinstance(result, dict) else {},
    )

    if config.VERBOSE:
        nav_type = result.get("nav_type", "unknown")
        routes   = len(result.get("routes", []))
        tabs     = len(result.get("bottom_tabs", []))
        print(f"      {nav_type} | {routes} routes | {tabs} bottom tabs")

    return result
