# ============================================================
# agents/assumption_generator.py
# ============================================================

import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _normalize(text: str) -> str:
    return text.strip().lower()


def _parse_screen_count(prompt: str) -> int | None:
    prompt_lower = _normalize(prompt)
    if "only 4 screens" in prompt_lower:
        return 4
    match = re.search(r"(\d+)\s+screens", prompt_lower)
    if match:
        return int(match.group(1))
    return None


def _parse_screen_names(prompt: str) -> list[str]:
    prompt_lower = _normalize(prompt)
    screens = []
    if "home" in prompt_lower:
        screens.append("Home")
    if "todo" in prompt_lower or "todos" in prompt_lower:
        screens.append("Todos")
    if "note" in prompt_lower or "notes" in prompt_lower:
        screens.append("Notes")
    if "setting" in prompt_lower or "settings" in prompt_lower:
        screens.append("Settings")
    if "profile" in prompt_lower:
        screens.append("Profile")
    if "dashboard" in prompt_lower:
        screens.append("Dashboard")

    if "only 4 screens" in prompt_lower:
        match = re.search(r"only\s+4\s+screens[,;:\s]*(.*)", prompt_lower)
        if match:
            names = re.split(r"[ ,;]+", match.group(1).strip())
            names = [name.capitalize() for name in names if name]
            if len(names) >= 4:
                screens = [name for name in names[:4]]
    return screens


def _local_storage_assumption(prompt: str, intent: dict) -> str:
    if intent.get("data_tier") == "local_only" or intent.get("needs_backend") is False:
        return (
            "Store and read photos from the device only using platform gallery APIs. "
            "No cloud database or user accounts."
        )
    return (
        "Use Firebase Cloud Firestore as the backend database. "
        "Use Firestore offline persistence for local caching only."
    )


def _authentication_assumption(prompt: str, intent: dict) -> str:
    prompt_lower = _normalize(prompt)
    if "no authentication" in prompt_lower or "no auth" in prompt_lower:
        return "Do not require user login or authentication."
    if intent.get("needs_auth") is False:
        return "Do not require user login or authentication."
    return "Use simple app access without authentication unless needed."


def _navigation_assumption(prompt: str) -> str:
    prompt_lower = _normalize(prompt)
    if "bottom" in prompt_lower or "navbar" in prompt_lower or "navigation" in prompt_lower:
        return "Use a simple bottom navigation bar for the main screens."
    return "Use a simple bottom navigation bar for the main screens."


def _has_local_only_requirements(prompt: str, intent: dict) -> bool:
    return intent.get("data_tier") == "local_only" or intent.get("needs_backend") is False


def _has_no_auth_requirement(prompt: str, intent: dict) -> bool:
    prompt_lower = _normalize(prompt)
    return (
        "no authentication" in prompt_lower
        or "no auth" in prompt_lower
        or intent.get("needs_auth") is False
    )


def generate_assumptions(prompt: str, intent: dict, clarifications: dict | None = None) -> dict:
    """Fill missing requirement context with simple assumptions for non-technical users."""
    clarifications = dict(clarifications or {})
    screen_names = _parse_screen_names(prompt)
    screen_count = _parse_screen_count(prompt)

    if not screen_names:
        screen_names = ["Home", "Todos", "Notes", "Settings"]

    assumptions = {
        "app_name": intent.get("app_name", "Your App"),
        "core_goal": intent.get("core_goal", "Build a simple app with clear features."),
        "domain": intent.get("domain", "general"),
        "screens": screen_names,
        "screen_count": screen_count or len(screen_names),
        "no_auth": _has_no_auth_requirement(prompt, intent),
        "no_backend": _has_local_only_requirements(prompt, intent),
        "data_storage": _local_storage_assumption(prompt, intent),
        "authentication": _authentication_assumption(prompt, intent),
        "navigation": _navigation_assumption(prompt),
        "user_experience": "Keep the UI simple and easy to use for non-technical students.",
        "notes": "Use plain text notes and a clean layout with familiar labels.",
    }

    clarifications["_assumptions"] = {
        "question": "assumptions",
        "answer": json.dumps(assumptions, indent=2),
    }
    clarifications["_assumptions_data"] = assumptions
    return clarifications
