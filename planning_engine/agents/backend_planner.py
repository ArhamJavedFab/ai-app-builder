# ============================================================
# agents/backend_planner.py
# ============================================================

import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.gemini_client import call_gemini_json
from core.prompt_loader import load_prompt_template
import config

BACKEND_PLANNER = load_prompt_template("backend_planner.md")


def _enforce_firebase_backend(result: dict) -> dict:
    firebase_services = set(result.get("firebase_services") or [])
    firebase_services.update({"firebase_auth", "cloud_firestore"})

    if result.get("file_storage") not in {"firebase_storage", "none"}:
        result["file_storage"] = "none"
    if result.get("file_storage") == "firebase_storage":
        firebase_services.add("firebase_storage")

    if result.get("push_notifications"):
        result["push_provider"] = "fcm"
        firebase_services.add("firebase_messaging")
    else:
        result["push_provider"] = "none"

    result["needs_backend"] = True
    result["backend_type"] = "firebase"
    result["auth_provider"] = "firebase_auth"
    result["api_endpoints"] = []
    result["firebase_services"] = sorted(firebase_services)
    result.setdefault("firestore_collections", [])
    result.setdefault("security_rules", [])
    result["environment_variables"] = [
        "FIREBASE_API_KEY",
        "FIREBASE_PROJECT_ID",
        "FIREBASE_APP_ID",
    ]
    return result


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
    result = _enforce_firebase_backend(call_gemini_json(filled, use_pro=False))

    if config.VERBOSE:
        backend_type = result.get("backend_type", "unknown")
        auth         = result.get("auth_provider", "none")
        endpoints    = len(result.get("api_endpoints", []))
        realtime     = "🔴 realtime" if result.get("realtime") else ""
        print(f"      {backend_type} | auth: {auth} | {endpoints} endpoints {realtime}")

    return result
