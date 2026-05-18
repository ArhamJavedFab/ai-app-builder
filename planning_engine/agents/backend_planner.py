# ============================================================
# agents/backend_planner.py
# ============================================================

import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.gemini_client import call_gemini_json
from core.prompt_templates import BACKEND_PLANNER
import config


def plan_backend(intent: dict, features: dict, screens: dict | None = None) -> dict:
    """
    Stage 6 — Plan backend type, auth, APIs, storage, etc.
    Returns full backend requirements dict.
    """
    if config.VERBOSE:
        print("  ⚙️   Planning backend...")

    filled = BACKEND_PLANNER.format(
        intent_json=json.dumps(intent, indent=2),
        features_json=json.dumps(features, indent=2),
        screens_json=json.dumps(screens or {}, indent=2),
    )
    result = call_gemini_json(filled, use_pro=False)

    if config.VERBOSE:
        backend_type = result.get("backend_type", "unknown")
        auth         = result.get("auth_provider", "none")
        endpoints    = len(result.get("api_endpoints", []))
        realtime     = "🔴 realtime" if result.get("realtime") else ""
        print(f"      {backend_type} | auth: {auth} | {endpoints} endpoints {realtime}")

    return result
