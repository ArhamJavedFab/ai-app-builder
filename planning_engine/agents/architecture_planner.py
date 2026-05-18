# ============================================================
# agents/architecture_planner.py
# ============================================================

import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.gemini_client import call_gemini_json
from core.prompt_templates import ARCHITECTURE_PLANNER, DESIGN_SYSTEM_PLANNER
import config


def plan_architecture(intent: dict, features: dict) -> dict:
    """
    Stage 8a — Plan Flutter architecture: state management, folder structure,
    dependencies, testing strategy, security + performance notes.
    Uses Gemini Pro for reasoning quality.
    """
    if config.VERBOSE:
        print("  🏗️   Planning Flutter architecture (using Pro model)...")

    filled = ARCHITECTURE_PLANNER.format(
        intent_json=json.dumps(intent, indent=2),
        features_json=json.dumps(features, indent=2),
    )
    result = call_gemini_json(filled, use_pro=True)

    if config.VERBOSE:
        state  = result.get("state_management", "unknown")
        arch   = result.get("architecture_pattern", "unknown")
        deps   = len(result.get("flutter_dependencies", []))
        print(f"      {state} | {arch} | {deps} dependencies")

    return result


def plan_design_system(intent: dict) -> dict:
    """
    Stage 8b — Generate Flutter design system (colors, fonts, spacing, theme).
    """
    if config.VERBOSE:
        print("  🎨  Planning design system...")

    filled = DESIGN_SYSTEM_PLANNER.format(
        intent_json=json.dumps(intent, indent=2),
        app_type=intent.get("app_type", ""),
        target_users=", ".join(intent.get("target_users", [])),
    )
    result = call_gemini_json(filled, use_pro=False)

    if config.VERBOSE:
        theme   = result.get("theme", "unknown")
        primary = result.get("primary_color", "?")
        fonts   = f"{result.get('font_family_display','?')} / {result.get('font_family_body','?')}"
        print(f"      Theme: {theme} | Color: {primary} | Fonts: {fonts}")

    return result
