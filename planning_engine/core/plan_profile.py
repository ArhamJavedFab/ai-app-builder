# ============================================================
# core/plan_profile.py — Intent-driven local vs Firebase profile
# ============================================================

from __future__ import annotations

import json
import re
from typing import Any

LOCAL_BACKEND_TYPE = "local"
LOCAL_NETWORK_LAYER = "device_storage"

CLOUD_HINTS = (
    "cloud", "firebase", "firestore", "sync", "backup", "online",
    "account", "login", "sign in", "signup", "multi-device", "server",
)
LOCAL_HINTS = (
    "local storage", "device storage", "on device", "offline only",
    "no account", "no login", "no auth", "viewing only", "view only",
    "device's local", "device local", "phone storage", "gallery only",
    "local only",
)

# Word-boundary matching — avoids "pics" matching inside "application"
MEDIA_HINTS = ("gallery", "photo", "photos", "pics", "picture", "pictures", "album", "image viewer")
ALARM_HINTS = ("alarm", "alarms", "clock", "timer", "timers", "snooze", "wake", "countdown")
NOTES_HINTS = ("notes", "note-taking", "notebook", "journal", "memo", "notepad", "diary")
TASK_HINTS = ("todo", "to-do", "task", "tasks", "habit", "habits", "planner", "reminder")

FIREBASE_PACKAGE_BLOCK = {
    "firebase_core", "firebase_auth", "cloud_firestore",
    "firebase_storage", "firebase_messaging",
    "dio", "http", "chopper",
}
GALLERY_ONLY_PACKAGES = {"photo_manager"}

GALLERY_TEXT_MARKERS = (
    "firestore", "firebase", "cloud_firestore", "photo_manager",
    "upload user media", "gallery", "photos", "reading media",
    "storage permissions before reading",
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _has_hint(text: str, hints: tuple[str, ...]) -> bool:
    """Match whole words/phrases, not accidental substrings."""
    for hint in hints:
        if " " in hint or "-" in hint:
            if hint in text:
                return True
        elif re.search(rf"\b{re.escape(hint)}\b", text):
            return True
    return False


def _build_context(
    intent: dict,
    user_prompt: str = "",
    clarifications: dict | None = None,
) -> str:
    parts = [
        _normalize(user_prompt),
        _clarification_text(clarifications),
        _normalize(intent.get("app_type", "")),
        _normalize(intent.get("core_goal", "")),
        _normalize(intent.get("summary", "")),
        " ".join(intent.get("detected_modules") or []),
    ]
    return _normalize(" ".join(p for p in parts if p))


def _clarification_text(clarifications: dict | None) -> str:
    if not clarifications:
        return ""
    parts: list[str] = []
    for key, entry in clarifications.items():
        if key.startswith("_"):
            continue
        if isinstance(entry, dict):
            parts.append(str(entry.get("question", "")))
            parts.append(str(entry.get("answer", "")))
        else:
            parts.append(str(entry))
    assumptions = clarifications.get("_assumptions_data")
    if isinstance(assumptions, dict):
        parts.append(json.dumps(assumptions))
    return _normalize(" ".join(parts))


def resolve_storage_profile(
    intent: dict,
    user_prompt: str = "",
    clarifications: dict | None = None,
) -> str:
    """
    Pick local storage stack: media | alarm | notes | tasks | generic.
    Uses intent.local_kind if already set, else infers from full context.
    """
    preset = (intent.get("local_kind") or intent.get("storage_profile") or "").lower()
    if preset in {"media", "alarm", "notes", "tasks", "generic"}:
        return preset

    context = _build_context(intent, user_prompt, clarifications)
    domain = (intent.get("domain") or "").lower()

    # Strongest signals first (word boundaries)
    if _has_hint(context, MEDIA_HINTS) or domain == "media":
        return "media"
    if _has_hint(context, ALARM_HINTS) or "alarm" in _normalize(intent.get("app_type", "")):
        return "alarm"
    if _has_hint(context, NOTES_HINTS) or "note" in _normalize(intent.get("app_type", "")):
        return "notes"
    if _has_hint(context, TASK_HINTS) or domain == "productivity":
        return "tasks"
    return "generic"


# Backwards-compatible alias
def resolve_local_kind(
    intent: dict,
    user_prompt: str = "",
    clarifications: dict | None = None,
) -> str:
    return resolve_storage_profile(intent, user_prompt, clarifications)


def resolve_data_tier(
    intent: dict,
    clarifications: dict | None = None,
    user_prompt: str = "",
) -> str:
    """Return 'local_only' or 'firebase'."""
    if intent.get("data_tier") in ("local_only", "firebase"):
        return intent["data_tier"]

    prompt = _normalize(user_prompt)
    context = _build_context(intent, user_prompt, clarifications)

    if intent.get("needs_backend") is False and intent.get("needs_auth") is False:
        return "local_only"

    if _has_hint(context, CLOUD_HINTS) and not _has_hint(context, LOCAL_HINTS):
        return "firebase"

    if intent.get("needs_backend") is True or intent.get("needs_auth") is True:
        return "firebase"

    if intent.get("domain") in {"productivity", "media"} and intent.get("complexity") == "simple":
        if not _has_hint(context, CLOUD_HINTS):
            return "local_only"

    if _has_hint(prompt, ALARM_HINTS) or _has_hint(prompt, NOTES_HINTS):
        return "local_only"

    return "firebase"


def is_local_first_plan(plan: dict) -> bool:
    tier = plan.get("data_tier")
    if tier == "local_only":
        return True
    if tier == "firebase":
        return False
    backend = plan.get("backend") or {}
    if backend.get("needs_backend") is False:
        return True
    return backend.get("backend_type") == LOCAL_BACKEND_TYPE


def enrich_intent_for_planners(
    intent: dict,
    clarifications: dict | None = None,
    user_prompt: str = "",
) -> dict:
    """Attach data_tier + storage profile for all downstream agents."""
    enriched = dict(intent)
    tier = resolve_data_tier(enriched, clarifications, user_prompt)
    enriched["data_tier"] = tier

    if tier == "local_only":
        enriched["needs_backend"] = False
        enriched["needs_auth"] = False
        enriched["needs_realtime"] = False
        enriched["needs_payments"] = False
        enriched["needs_admin"] = False
        profile = resolve_storage_profile(enriched, user_prompt, clarifications)
        enriched["local_kind"] = profile
        enriched["storage_profile"] = profile
        enriched["needs_local_database"] = profile != "generic" or bool(
            enriched.get("detected_modules")
        )
    else:
        enriched["needs_local_database"] = True
        enriched["storage_profile"] = "firebase"

    return enriched


def _local_profile(profile: str) -> dict[str, Any]:
    if profile == "media":
        return {
            "local_database": "device_gallery",
            "cache_strategy": "Use photo_manager to index on-device photos; no cloud database.",
            "security_rules": [
                "Request gallery/storage permissions before reading media.",
                "Do not upload user photos without explicit opt-in.",
            ],
            "dependencies": [
                ("photo_manager", "Read device photos and albums."),
                ("permission_handler", "Request gallery/storage permissions."),
                ("path_provider", "Resolve local media file paths."),
            ],
            "database_label": "on-device gallery index",
        }
    if profile == "alarm":
        return {
            "local_database": "isar",
            "cache_strategy": (
                "Persist alarms and settings in Isar; schedule with "
                "flutter_local_notifications and timezone."
            ),
            "security_rules": [
                "Store alarm data only on-device; no cloud sync for MVP.",
                "Request notification permissions before scheduling alarms.",
            ],
            "dependencies": [
                ("isar", "Structured local storage for alarms and settings."),
                ("isar_flutter_libs", "Isar Flutter bindings."),
                ("path_provider", "App documents directory for the Isar database."),
                ("flutter_local_notifications", "Show and schedule alarm notifications."),
                ("timezone", "Timezone-aware alarm scheduling."),
                ("permission_handler", "Notification permissions."),
            ],
            "database_label": "local Isar (alarms)",
        }
    if profile == "notes":
        return {
            "local_database": "isar",
            "cache_strategy": "Persist notes and folders locally with Isar.",
            "security_rules": [
                "Keep notes on-device unless the user enables cloud sync later.",
                "Optional backup export only with explicit user action.",
            ],
            "dependencies": [
                ("isar", "Structured storage for notes and metadata."),
                ("isar_flutter_libs", "Isar Flutter bindings."),
                ("path_provider", "Local database file location."),
            ],
            "database_label": "local Isar (notes)",
        }
    if profile == "tasks":
        return {
            "local_database": "hive",
            "cache_strategy": "Persist tasks and habits locally with Hive.",
            "security_rules": [
                "Store tasks on-device; no account required for MVP.",
            ],
            "dependencies": [
                ("hive", "Local storage for tasks and settings."),
                ("hive_flutter", "Hive Flutter integration."),
                ("path_provider", "App storage paths."),
            ],
            "database_label": "local Hive (tasks)",
        }
    return {
        "local_database": "hive",
        "cache_strategy": "Use Hive for simple on-device persistence.",
        "security_rules": [
            "Keep user data on-device unless cloud sync is added later.",
        ],
        "dependencies": [
            ("hive", "Lightweight local storage."),
            ("hive_flutter", "Hive Flutter integration."),
            ("path_provider", "Local app storage paths."),
        ],
        "database_label": "local Hive",
    }


def build_local_backend(profile: str = "generic") -> dict:
    spec = _local_profile(profile)
    needs_notifications = profile == "alarm"
    return {
        "needs_backend": False,
        "backend_type": LOCAL_BACKEND_TYPE,
        "realtime": False,
        "realtime_reason": "Local-only app; no server sync required.",
        "auth_provider": "none",
        "auth_methods": [],
        "file_storage": "device",
        "push_notifications": needs_notifications,
        "push_provider": "local_notifications" if needs_notifications else "none",
        "caching": True,
        "background_jobs": needs_notifications,
        "needs_payment_gateway": False,
        "payment_method": "none",
        "firebase_services": [],
        "firestore_collections": [],
        "security_rules": list(spec["security_rules"]),
        "third_party_apis": [],
        "api_endpoints": [],
        "environment_variables": [],
        "storage_profile": profile,
    }


def build_local_architecture_patch(profile: str = "generic") -> dict:
    spec = _local_profile(profile)
    return {
        "network_layer": LOCAL_NETWORK_LAYER,
        "local_database": spec["local_database"],
        "offline_first": True,
        "cart_strategy": "local",
        "storage_profile": profile,
    }


def local_database_plan(profile: str = "generic") -> dict:
    spec = _local_profile(profile)
    return {
        "database_type": "local",
        "tables": [],
        "local_cache_strategy": spec["cache_strategy"],
        "label": spec["database_label"],
    }


def _is_gallery_leak(text: str) -> bool:
    lower = text.lower()
    return any(marker in lower for marker in GALLERY_TEXT_MARKERS)


def _filter_bad_text(items: list, profile: str) -> list:
    if profile == "media":
        return list(items)
    return [i for i in items if not _is_gallery_leak(str(i))]


def sanitize_local_plan(plan: dict[str, Any], profile: str = "generic") -> None:
    """Force consistent local stack; remove gallery/Firebase leakage for non-media apps."""
    spec = _local_profile(profile)

    for key in ("security_rules", "performance_notes", "accessibility_notes", "edge_cases"):
        if isinstance(plan.get(key), list):
            plan[key] = _filter_bad_text(plan[key], profile)

    backend = plan.get("backend")
    if isinstance(backend, dict):
        backend.update(build_local_backend(profile))
        backend["security_rules"] = list(spec["security_rules"])

    arch = dict(plan.get("flutter_architecture") or {})
    arch.update(build_local_architecture_patch(profile))
    plan["flutter_architecture"] = arch
    plan["storage_profile"] = profile

    blocked = FIREBASE_PACKAGE_BLOCK | (GALLERY_ONLY_PACKAGES if profile != "media" else set())
    plan["flutter_dependencies"] = [
        dep for dep in (plan.get("flutter_dependencies") or [])
        if str(dep.get("package", "")).lower() not in blocked
    ]
    existing = {str(d.get("package", "")).lower() for d in plan["flutter_dependencies"]}
    for package, purpose in spec["dependencies"]:
        if package not in existing:
            plan["flutter_dependencies"].append({
                "package": package,
                "version": "latest",
                "purpose": purpose,
            })
            existing.add(package)


def apply_local_first_to_plan_dict(
    plan: dict[str, Any],
    intent: dict | None = None,
    user_prompt: str = "",
    clarifications: dict | None = None,
) -> None:
    """Apply the correct local profile across backend, arch, and deps."""
    intent = intent or {}
    profile = (
        intent.get("storage_profile")
        or intent.get("local_kind")
        or resolve_storage_profile(intent, user_prompt, clarifications)
    )
    plan["data_tier"] = "local_only"
    plan["storage_profile"] = profile
    plan["backend"] = build_local_backend(profile)
    plan["database_tables"] = []
    arch = dict(plan.get("flutter_architecture") or {})
    arch.update(build_local_architecture_patch(profile))
    plan["flutter_architecture"] = arch
    sanitize_local_plan(plan, profile)


def apply_local_architecture_result(result: dict, intent: dict) -> dict:
    """Overwrite LLM architecture output with the intent storage profile."""
    profile = (
        intent.get("storage_profile")
        or intent.get("local_kind")
        or resolve_storage_profile(intent)
    )
    result.update(build_local_architecture_patch(profile))
    result["offline_first"] = True
    if result.get("cart_strategy") in ("firestore", "server"):
        result["cart_strategy"] = "local"

    spec = _local_profile(profile)
    blocked = FIREBASE_PACKAGE_BLOCK | (GALLERY_ONLY_PACKAGES if profile != "media" else set())
    deps = [
        d for d in result.get("flutter_dependencies", [])
        if str(d.get("package", "")).lower() not in blocked
    ]
    existing = {str(d.get("package", "")).lower() for d in deps}
    for package, purpose in spec["dependencies"]:
        if package not in existing:
            deps.append({"package": package, "version": "latest", "purpose": purpose})
    result["flutter_dependencies"] = deps

    if isinstance(result.get("security_rules"), list):
        result["security_rules"] = _filter_bad_text(result["security_rules"], profile)
    if isinstance(result.get("performance_notes"), list):
        result["performance_notes"] = _filter_bad_text(result["performance_notes"], profile)

    return result


def reconcile_plan_with_intent(
    plan: dict[str, Any],
    intent: dict,
    user_prompt: str = "",
    clarifications: dict | None = None,
) -> None:
    """Re-apply tier + storage profile after any stage that may pollute the plan."""
    tier = intent.get("data_tier") or resolve_data_tier(intent, clarifications, user_prompt)
    plan["data_tier"] = tier
    if tier == "local_only":
        apply_local_first_to_plan_dict(plan, intent, user_prompt, clarifications)
