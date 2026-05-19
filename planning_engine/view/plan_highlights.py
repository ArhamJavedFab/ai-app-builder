from __future__ import annotations

from typing import Any


def _feature_names(plan: dict[str, Any], limit: int = 6) -> list[str]:
    names: list[str] = []
    for module in plan.get("features", []):
        for item in module.get("items", []):
            name = item.get("name")
            if name:
                names.append(str(name))
            if len(names) >= limit:
                return names
    return names


def _screen_names(plan: dict[str, Any], limit: int = 5) -> list[str]:
    return [
        str(screen.get("name"))
        for screen in plan.get("screens", [])[:limit]
        if screen.get("name")
    ]


def build_plain_language_highlights(plan: dict[str, Any]) -> list[str]:
    """Create short, non-technical highlights for the chat response."""
    app_name = plan.get("app_name") or "Your app"
    app_type = plan.get("app_type") or "app"
    users = ", ".join(plan.get("target_users", [])[:3]) or "your users"
    features = _feature_names(plan)
    screens = _screen_names(plan)
    backend = plan.get("backend", {})
    design = plan.get("design_system", {})

    highlights = [
        f"{app_name} is planned as a {app_type}.",
        f"It is mainly for {users}.",
    ]

    if features:
        highlights.append(f"Main features: {', '.join(features)}.")
    if screens:
        highlights.append(f"Key screens include {', '.join(screens)}.")

    backend_type = backend.get("backend_type") or "Firebase"
    auth = backend.get("auth_provider") or "Firebase Auth"
    highlights.append(f"Backend uses {backend_type} with {auth}.")

    collections = backend.get("firestore_collections") or [
        table.get("name") for table in plan.get("database_tables", []) if table.get("name")
    ]
    if collections:
        highlights.append(f"Data is organized around {', '.join(collections[:5])}.")

    theme = design.get("theme")
    primary = design.get("primary_color")
    if theme or primary:
        highlights.append(f"Design style is {theme or 'modern'} with {primary or 'a clear primary color'}.")

    if plan.get("validation_passed"):
        highlights.append("The plan passed validation.")
    else:
        highlights.append("The plan was generated, but validation found items to review.")

    return highlights
