# ============================================================
# agents/intent_analyzer.py
# ============================================================

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config
from core.gemini_client import call_gemini_json
from core.prompt_loader import load_prompt_template

INTENT_ANALYZER = load_prompt_template("intent_analyzer.md")

VALID_DOMAINS = frozenset({
    "ecommerce",
    "social",
    "productivity",
    "health",
    "education",
    "finance",
    "food_delivery",
    "transport",
    "marketplace",
    "entertainment",
    "media",
    "saas",
    "other",
})

VALID_COMPLEXITY = frozenset({"simple", "medium", "complex", "enterprise"})

DOMAIN_ALIASES = {
    "unknown": "other",
    "general": "other",
    "picture_gallery": "media",
    "photo_gallery": "media",
    "photos": "media",
    "gallery": "media",
    "images": "media",
    "utilities": "productivity",
    "utility": "productivity",
    "lifestyle": "productivity",
    "shopping": "ecommerce",
    "retail": "ecommerce",
    "dating": "social",
    "messaging": "social",
    "streaming": "entertainment",
    "gaming": "entertainment",
    "fitness": "health",
    "wellness": "health",
    "learning": "education",
    "banking": "finance",
    "delivery": "food_delivery",
    "rideshare": "transport",
    "ride_sharing": "transport",
    "b2b": "saas",
}


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower().strip())


def _unwrap_intent_result(raw: dict | list | None) -> dict:
    """Extract intent dict from common LLM wrapper shapes."""
    if raw is None:
        return {}
    if isinstance(raw, list):
        raw = raw[0] if raw and isinstance(raw[0], dict) else {}
    if not isinstance(raw, dict):
        return {}

    for key in ("intent_json", "intent", "analysis", "result", "data", "output"):
        nested = raw.get(key)
        if isinstance(nested, dict):
            if any(k in nested for k in ("domain", "app_type", "complexity", "core_goal")):
                return nested

    return raw


def _coerce_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return default


def _coerce_confidence(value: object) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, score))


def _normalize_domain(domain: object) -> str:
    raw = _normalize_text(str(domain or ""))
    raw = raw.replace("-", "_").replace(" ", "_")
    if raw in VALID_DOMAINS:
        return raw
    if raw in DOMAIN_ALIASES:
        return DOMAIN_ALIASES[raw]
    return "other"


def _normalize_complexity(complexity: object) -> str:
    raw = _normalize_text(str(complexity or ""))
    if raw in VALID_COMPLEXITY:
        return raw
    if raw in {"low", "basic", "minimal"}:
        return "simple"
    if raw in {"moderate", "mid", "standard"}:
        return "medium"
    if raw in {"high", "advanced"}:
        return "complex"
    return "simple"


def _as_string_list(value: object) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return []


def _intent_is_weak(intent: dict) -> bool:
    domain = _normalize_domain(intent.get("domain"))
    confidence = _coerce_confidence(intent.get("confidence"))
    app_type = (intent.get("app_type") or "").strip().lower()
    return (
        domain == "other"
        and confidence < 0.35
        and (not app_type or app_type in {"unknown", "unknown app concept", "general mobile app"})
    )


def _rule_based_intent(prompt: str) -> dict:
    """Deterministic classification when the LLM returns empty or vague intent."""
    text = _normalize_text(prompt)

    def _base(**overrides: object) -> dict:
        data = {
            "app_name": "",
            "domain": "other",
            "app_type": "mobile app",
            "platform": "flutter_cross_platform",
            "complexity": "simple",
            "core_goal": "Deliver the core experience described by the user.",
            "target_users": ["general users"],
            "user_roles": ["user"],
            "detected_modules": ["core_features"],
            "needs_backend": False,
            "needs_realtime": False,
            "needs_auth": False,
            "needs_payments": False,
            "needs_admin": False,
            "confidence": 0.72,
            "tagline": "",
        }
        data.update(overrides)
        return data

    gallery_terms = (
        "gallery", "pics", "photo", "photos", "picture", "pictures",
        "image viewer", "album", "camera roll", "snap",
    )
    if any(term in text for term in gallery_terms):
        return _base(
            app_name="PicFlow",
            domain="media",
            app_type="photo gallery app",
            complexity="simple",
            core_goal="Let users browse and view photos on their device in a simple gallery.",
            detected_modules=[
                "gallery_grid",
                "album_browser",
                "full_screen_viewer",
                "local_storage_access",
            ],
            needs_backend=any(w in text for w in ("cloud", "sync", "backup", "firebase", "online")),
            needs_auth=any(w in text for w in ("login", "account", "sign in", "signup", "user profile")),
            confidence=0.8,
            tagline="Your photos, organized beautifully.",
        )

    if any(w in text for w in ("food", "restaurant", "delivery", "order meal", "takeaway")):
        return _base(
            domain="food_delivery",
            app_type="food delivery app",
            complexity="medium",
            core_goal="Connect customers with restaurants for ordering and delivery.",
            target_users=["customers", "restaurants"],
            user_roles=["customer", "restaurant_owner"],
            detected_modules=["restaurant_catalog", "cart", "checkout", "order_tracking"],
            needs_backend=True,
            needs_realtime="track" in text or "live" in text,
            needs_auth=True,
            needs_payments=any(w in text for w in ("pay", "payment", "stripe", "card")),
            confidence=0.78,
        )

    if any(w in text for w in ("shop", "store", "ecommerce", "e-commerce", "product catalog", "cart")):
        return _base(
            domain="ecommerce",
            app_type="ecommerce shopping app",
            complexity="medium",
            detected_modules=["product_catalog", "cart", "checkout"],
            needs_backend=True,
            needs_auth=True,
            needs_payments=True,
            confidence=0.75,
        )

    if any(w in text for w in ("alarm", "clock", "timer", "snooze", "wake up", "wake-up")):
        return _base(
            app_name="Chime",
            domain="productivity",
            app_type="alarm clock app",
            complexity="simple",
            core_goal="Let users set recurring alarms with reliable local notifications.",
            detected_modules=[
                "alarm_list",
                "alarm_create_edit",
                "recurring_schedules",
                "local_notifications",
                "settings",
            ],
            needs_backend=False,
            needs_auth=False,
            confidence=0.82,
            tagline="Never miss the moment.",
            local_kind="alarm",
            storage_profile="alarm",
        )

    if any(w in text for w in ("note", "notes", "journal", "diary", "memo", "notepad")):
        return _base(
            app_name="NotePad",
            domain="productivity",
            app_type="notes app",
            complexity="simple",
            core_goal="Let users write, organize, and find notes on their device.",
            detected_modules=["note_editor", "note_list", "folders", "search"],
            needs_backend=False,
            needs_auth=False,
            confidence=0.8,
            storage_profile="notes",
            local_kind="notes",
        )

    if any(w in text for w in ("todo", "task", "habit", "planner", "reminder")):
        return _base(
            domain="productivity",
            app_type="productivity app",
            complexity="simple",
            detected_modules=["task_list", "reminders", "progress_tracking"],
            confidence=0.74,
            storage_profile="tasks",
            local_kind="tasks",
        )

    if any(w in text for w in ("chat", "social", "feed", "friends", "post", "community")):
        return _base(
            domain="social",
            app_type="social app",
            complexity="medium",
            needs_backend=True,
            needs_auth=True,
            needs_realtime="chat" in text or "message" in text,
            confidence=0.73,
        )

    if any(w in text for w in ("ride", "taxi", "driver", "transport", "uber")):
        return _base(
            domain="transport",
            app_type="ride-hailing app",
            complexity="complex",
            needs_backend=True,
            needs_realtime=True,
            needs_auth=True,
            confidence=0.76,
        )

    if any(w in text for w in ("fitness", "workout", "health", "steps", "calories")):
        return _base(
            domain="health",
            app_type="health and fitness app",
            complexity="medium",
            confidence=0.72,
        )

    if any(w in text for w in ("course", "learn", "lesson", "quiz", "education")):
        return _base(
            domain="education",
            app_type="learning app",
            complexity="medium",
            confidence=0.72,
        )

    if any(w in text for w in ("budget", "expense", "finance", "wallet", "bank")):
        return _base(
            domain="finance",
            app_type="personal finance app",
            complexity="medium",
            needs_auth=True,
            confidence=0.73,
        )

    if len(text.split()) >= 4:
        return _base(confidence=0.55)

    return _base(confidence=0.25)


def normalize_intent(raw: dict | list | None, prompt: str = "") -> dict:
    """Normalize LLM or fallback output to the canonical intent contract."""
    data = _unwrap_intent_result(raw)

    fallback = _rule_based_intent(prompt) if prompt else {}

    domain = _normalize_domain(data.get("domain"))
    complexity = _normalize_complexity(data.get("complexity"))
    confidence = _coerce_confidence(data.get("confidence"))

    if domain == "other" and fallback.get("domain") not in ("other", None):
        if _intent_is_weak(data) or confidence < 0.4:
            domain = fallback["domain"]

    if complexity == "simple" and confidence < 0.4 and fallback.get("complexity"):
        complexity = _normalize_complexity(fallback.get("complexity"))

    app_name = (data.get("app_name") or "").strip() or fallback.get("app_name", "")
    app_type = (data.get("app_type") or "").strip() or fallback.get("app_type", "mobile app")
    core_goal = (data.get("core_goal") or "").strip() or fallback.get("core_goal", "")

    target_users = _as_string_list(data.get("target_users")) or fallback.get("target_users", [])
    user_roles = _as_string_list(data.get("user_roles")) or fallback.get("user_roles", ["user"])
    detected_modules = _as_string_list(data.get("detected_modules")) or fallback.get("detected_modules", [])

    if confidence < 0.35 and fallback.get("confidence", 0) > confidence:
        confidence = float(fallback["confidence"])

    if not core_goal and prompt:
        core_goal = fallback.get("core_goal") or f"Build a Flutter app based on: {prompt[:120]}"

    tagline = (data.get("tagline") or "").strip() or fallback.get("tagline", "")

    def _flag(key: str) -> bool:
        if key in data:
            return _coerce_bool(data.get(key))
        return bool(fallback.get(key, False))

    storage_profile = (
        data.get("storage_profile")
        or fallback.get("storage_profile")
        or ""
    )
    local_kind = data.get("local_kind") or fallback.get("local_kind") or storage_profile

    return {
        "app_name": app_name,
        "domain": domain,
        "app_type": app_type,
        "platform": data.get("platform") or "flutter_cross_platform",
        "complexity": complexity,
        "core_goal": core_goal,
        "target_users": target_users,
        "user_roles": user_roles,
        "detected_modules": detected_modules,
        "needs_backend": _flag("needs_backend"),
        "needs_realtime": _flag("needs_realtime"),
        "needs_auth": _flag("needs_auth"),
        "needs_payments": _flag("needs_payments"),
        "needs_admin": _flag("needs_admin"),
        "confidence": confidence,
        "tagline": tagline,
        "storage_profile": storage_profile,
        "local_kind": local_kind,
    }


def analyze_intent(prompt: str, *, use_fallback: bool = True) -> dict:
    """
    Stage 1 — Understand what the user wants to build.
    Returns a dict describing domain, complexity, modules, confidence, etc.
    """
    if config.VERBOSE:
        print("  🔍  Analyzing intent...")

    filled_prompt = INTENT_ANALYZER.format(prompt=prompt)
    raw: dict | list = {}
    try:
        raw = call_gemini_json(filled_prompt, use_pro=False)
    except Exception as e:
        if config.VERBOSE:
            print(f"      ⚠️  Intent LLM failed: {e}")
        if not use_fallback:
            raise

    result = normalize_intent(raw, prompt)

    if use_fallback and _intent_is_weak(result):
        merged = normalize_intent(_rule_based_intent(prompt), prompt)
        for key, value in merged.items():
            if not result.get(key) or result.get(key) in ("", [], "other", 0.0):
                result[key] = value
            elif key == "domain" and result.get("domain") == "other" and value != "other":
                result[key] = value
            elif key == "confidence" and _coerce_confidence(result.get("confidence")) < 0.4:
                result[key] = value
        result = normalize_intent(result, prompt)

    if config.VERBOSE:
        confidence = result.get("confidence", 0)
        domain = result.get("domain", "other")
        complexity = result.get("complexity", "simple")
        print(f"      Domain: {domain} | Complexity: {complexity} | Confidence: {confidence:.0%}")

    return result
