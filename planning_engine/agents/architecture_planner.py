# ============================================================
# agents/architecture_planner.py
# ============================================================

import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.gemini_client import call_gemini_json
from core.prompt_templates import ARCHITECTURE_PLANNER, DESIGN_SYSTEM_PLANNER
import config


def _dependency_names(dependencies: list[dict]) -> set[str]:
    return {str(dep.get("package", "")).lower() for dep in dependencies}


def _ensure_dependency(dependencies: list[dict], package: str, purpose: str) -> None:
    if package.lower() in _dependency_names(dependencies):
        return
    dependencies.append({"package": package, "version": "latest", "purpose": purpose})


def _enforce_firebase_architecture(result: dict, backend: dict | None = None) -> dict:
    result["network_layer"] = "firebase_sdk"
    result["local_database"] = "firestore_offline_cache"
    if result.get("cart_strategy") == "server":
        result["cart_strategy"] = "firestore"

    dependencies = result.setdefault("flutter_dependencies", [])
    _ensure_dependency(dependencies, "firebase_core", "Initialize Firebase in Flutter.")
    _ensure_dependency(dependencies, "firebase_auth", "Firebase Authentication.")
    _ensure_dependency(dependencies, "cloud_firestore", "Cloud Firestore data access.")

    firebase_services = set((backend or {}).get("firebase_services", []))
    if "firebase_storage" in firebase_services:
        _ensure_dependency(dependencies, "firebase_storage", "Firebase Storage uploads.")
    if "firebase_messaging" in firebase_services:
        _ensure_dependency(dependencies, "firebase_messaging", "FCM push notifications.")

    result["flutter_dependencies"] = [
        dep for dep in dependencies
        if str(dep.get("package", "")).lower() not in {
            "dio",
            "http",
            "chopper",
            "flutter_secure_storage",
            "isar",
            "isar_flutter_libs",
            "sqflite",
            "drift",
            "hive",
        }
    ]
    return result


def plan_architecture(intent: dict, features: dict, backend: dict | None = None) -> dict:
    """
    Stage 8a — Plan Flutter architecture.
    Passes backend context so cart_strategy can be set consistently.
    Uses Gemini Pro for reasoning quality.
    """
    if config.VERBOSE:
        print("  🏗️   Planning Flutter architecture (using Pro model)...")

    # Build augmented intent that includes backend cart decisions
    augmented_intent = dict(intent)
    if backend:
        has_cart_endpoint = any(
            "cart" in ep.get("path", "").lower()
            for ep in backend.get("api_endpoints", [])
        )
        augmented_intent["_cart_has_backend_endpoint"] = has_cart_endpoint
        augmented_intent["_payment_method"] = backend.get("payment_method", "")

    filled = ARCHITECTURE_PLANNER.format(
        intent_json=json.dumps(augmented_intent, indent=2),
        features_json=json.dumps(features, indent=2),
    )
    result = _enforce_firebase_architecture(call_gemini_json(filled, use_pro=True), backend)

    if config.VERBOSE:
        state  = result.get("state_management", "unknown")
        arch   = result.get("architecture_pattern", "unknown")
        deps   = len(result.get("flutter_dependencies", []))
        cart   = result.get("cart_strategy", "unknown")
        print(f"      {state} | {arch} | {deps} dependencies | cart: {cart}")

    return result


def _extract_branding_notes(clarifications: dict) -> str:
    """
    Pull any visual/color/style answers from clarifications to give
    the design system agent explicit instructions rather than letting
    it guess from the app type alone.
    """
    notes = []
    for qid, val in clarifications.items():
        question = val.get("question", "").lower()
        answer   = val.get("answer", "")
        if any(k in question for k in ("color", "style", "brand", "visual", "design", "theme")):
            notes.append(f"User said: \"{answer}\"")
    return "\n".join(notes) if notes else "No specific branding preferences given — use sensible defaults."


def plan_design_system(intent: dict, clarifications: dict | None = None) -> dict:
    """
    Stage 8b — Generate Flutter design system.
    Extracts branding notes from clarifications so user-specified
    colors and styles are always honoured.
    """
    if config.VERBOSE:
        print("  🎨  Planning design system...")

    branding_notes = _extract_branding_notes(clarifications or {})

    filled = DESIGN_SYSTEM_PLANNER.format(
        intent_json=json.dumps(intent, indent=2),
        app_type=intent.get("app_type", ""),
        target_users=", ".join(intent.get("target_users", [])),
        branding_notes=branding_notes,
    )
    result = call_gemini_json(filled, use_pro=False)

    if config.VERBOSE:
        theme   = result.get("theme", "unknown")
        primary = result.get("primary_color", "?")
        bg      = result.get("background_color", "?")
        fonts   = f"{result.get('font_family_display','?')} / {result.get('font_family_body','?')}"
        print(f"      Theme: {theme} | Primary: {primary} | BG: {bg} | Fonts: {fonts}")

    return result
