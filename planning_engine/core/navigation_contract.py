# ============================================================
# core/navigation_contract.py — Codegen-ready navigation contract
# ============================================================

from __future__ import annotations

import copy
import re
from typing import Any

HOME_ROUTE = "/home"
ROOT_ROUTE = "/"
SPLASH_ROUTE = "/splash"
ONBOARDING_ROUTE = "/onboarding"
PERMISSIONS_ROUTE = "/permissions"
ERROR_ROUTE = "/error"

# Screens that must never become the home shell when remapping "/".
_NON_HOME_ROUTE_EXACT = frozenset({
    SPLASH_ROUTE,
    ONBOARDING_ROUTE,
    PERMISSIONS_ROUTE,
    ERROR_ROUTE,
    "/login",
    "/signup",
})

_NON_HOME_NAME_HINTS = (
    "splash",
    "onboarding",
    "permission",
    "login",
    "signup",
    "signin",
    "error",
    "auth",
)


def _is_home_shell_screen(screen: dict[str, Any]) -> bool:
    route = (screen.get("route") or "").strip()
    if route in _NON_HOME_ROUTE_EXACT:
        return False
    name = (screen.get("name") or "").lower()
    if any(hint in name for hint in _NON_HOME_NAME_HINTS):
        return False
    if route == ROOT_ROUTE:
        return True
    if route == HOME_ROUTE:
        return True
    if "home" in name or "list" in name or "main" in name or "dashboard" in name:
        return True
    return False


def rewrite_root_route_to_home(screens: list[dict[str, Any]]) -> bool:
    """
    Replace bare ``/`` with ``/home`` on the primary shell screen.
    Returns True if any screen route was changed.
    """
    changed = False
    root_screens = [
        s for s in screens
        if isinstance(s, dict) and (s.get("route") or "").strip() == ROOT_ROUTE
    ]
    if not root_screens:
        return False

    target = next((s for s in root_screens if _is_home_shell_screen(s)), root_screens[0])
    for screen in root_screens:
        if screen is target:
            screen["route"] = HOME_ROUTE
            changed = True
        else:
            slug = re.sub(
                r"[^a-z0-9]+",
                "_",
                (screen.get("name") or "screen").lower().replace("screen", ""),
            ).strip("_")
            screen["route"] = f"/{slug or 'screen'}"
            changed = True
    return changed


def _replace_route_ref(value: str, route_map: dict[str, str]) -> str:
    return route_map.get(value, value)


def _replace_route_in_list(items: list[Any], route_map: dict[str, str]) -> list[Any]:
    out: list[Any] = []
    for item in items:
        if isinstance(item, str):
            out.append(_replace_route_ref(item, route_map))
        else:
            out.append(item)
    return out


def _apply_route_map_to_navigation(nav: dict[str, Any], route_map: dict[str, str]) -> None:
    if not route_map:
        return
    for route in nav.get("routes", []):
        if not isinstance(route, dict):
            continue
        path = route.get("path", "")
        if path in route_map:
            route["path"] = route_map[path]
    for tab in nav.get("bottom_tabs", []):
        if isinstance(tab, dict):
            r = tab.get("route", "")
            if r in route_map:
                tab["route"] = route_map[r]
    nav["protected_routes"] = _replace_route_in_list(
        nav.get("protected_routes") or [], route_map
    )
    nav["guest_routes"] = _replace_route_in_list(
        nav.get("guest_routes") or [], route_map
    )
    initial = nav.get("initial_route", "")
    if initial in route_map:
        nav["initial_route"] = route_map[initial]
    for redirect in nav.get("redirects") or []:
        if not isinstance(redirect, dict):
            continue
        for key in ("from", "to"):
            val = redirect.get(key, "")
            if val in route_map:
                redirect[key] = route_map[val]


def _apply_route_map_to_flows(flows: list[Any], route_map: dict[str, str]) -> None:
    for flow in flows:
        if not isinstance(flow, dict):
            continue
        steps = flow.get("steps")
        if isinstance(steps, list):
            flow["steps"] = [
                _replace_route_ref(s, route_map) if isinstance(s, str) else s
                for s in steps
            ]


def _screen_routes(screens: list[dict[str, Any]]) -> set[str]:
    return {
        (s.get("route") or "").strip()
        for s in screens
        if isinstance(s, dict) and (s.get("route") or "").strip()
    }


def _infer_initial_route(routes: set[str]) -> str:
    if SPLASH_ROUTE in routes:
        return SPLASH_ROUTE
    if ONBOARDING_ROUTE in routes:
        return ONBOARDING_ROUTE
    if HOME_ROUTE in routes:
        return HOME_ROUTE
    return sorted(routes)[0] if routes else ""


def _default_redirects(routes: set[str]) -> list[dict[str, str]]:
    redirects: list[dict[str, str]] = []
    if SPLASH_ROUTE not in routes:
        return redirects

    if ONBOARDING_ROUTE in routes:
        redirects.append({
            "from": SPLASH_ROUTE,
            "when": "first_launch",
            "to": ONBOARDING_ROUTE,
        })
    if PERMISSIONS_ROUTE in routes:
        redirects.append({
            "from": SPLASH_ROUTE,
            "when": "permissions_not_granted",
            "to": PERMISSIONS_ROUTE,
        })
        if HOME_ROUTE in routes:
            redirects.append({
                "from": PERMISSIONS_ROUTE,
                "when": "permissions_granted",
                "to": HOME_ROUTE,
            })
    if HOME_ROUTE in routes:
        redirects.append({
            "from": SPLASH_ROUTE,
            "when": "permissions_granted",
            "to": HOME_ROUTE,
        })
        if ONBOARDING_ROUTE not in routes and PERMISSIONS_ROUTE not in routes:
            redirects.append({
                "from": SPLASH_ROUTE,
                "when": "ready",
                "to": HOME_ROUTE,
            })
    return redirects


def _merge_redirects(existing: list[Any], defaults: list[dict[str, str]]) -> list[dict[str, str]]:
    merged: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    def add(item: dict[str, str]) -> None:
        key = (item.get("from", ""), item.get("when", ""), item.get("to", ""))
        if not key[0] or not key[2] or key in seen:
            return
        seen.add(key)
        merged.append({
            "from": key[0],
            "when": key[1] or "default",
            "to": key[2],
        })

    for raw in existing or []:
        if isinstance(raw, dict):
            add({
                "from": str(raw.get("from", "")).strip(),
                "when": str(raw.get("when", "")).strip(),
                "to": str(raw.get("to", "")).strip(),
            })
    for item in defaults:
        add(item)
    return merged


def _ensure_route_entries(
    nav: dict[str, Any],
    screens: list[dict[str, Any]],
) -> None:
    """Ensure navigation.routes has an entry for every screen route."""
    routes_list = nav.setdefault("routes", [])
    if not isinstance(routes_list, list):
        nav["routes"] = routes_list = []

    by_path = {
        (r.get("path") or "").strip(): r
        for r in routes_list
        if isinstance(r, dict) and (r.get("path") or "").strip()
    }

    for screen in screens:
        if not isinstance(screen, dict):
            continue
        path = (screen.get("route") or "").strip()
        if not path or path in by_path:
            continue
        routes_list.append({
            "path": path,
            "screen": screen.get("name", ""),
            "protected": bool(screen.get("is_protected", False)),
            "params": _path_params(path),
        })
        by_path[path] = routes_list[-1]


def _path_params(path: str) -> list[str]:
    params: list[str] = []
    for part in path.strip("/").split("/"):
        if part.startswith(":"):
            params.append(part[1:])
    return params


def finalize_navigation(
    screens: list[dict[str, Any]],
    navigation: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Apply codegen navigation contract:
    - ``/`` → ``/home`` on shell screen
    - ``initial_route`` + ``redirects``
    - sync nav route paths with screens
    """
    screens_copy = [copy.deepcopy(s) for s in screens if isinstance(s, dict)]
    nav = copy.deepcopy(navigation) if isinstance(navigation, dict) else {}

    route_map: dict[str, str] = {}
    if rewrite_root_route_to_home(screens_copy):
        route_map[ROOT_ROUTE] = HOME_ROUTE

    _apply_route_map_to_navigation(nav, route_map)
    _ensure_route_entries(nav, screens_copy)

    routes = _screen_routes(screens_copy)
    if not nav.get("initial_route"):
        nav["initial_route"] = _infer_initial_route(routes)

    defaults = _default_redirects(routes)
    nav["redirects"] = _merge_redirects(nav.get("redirects"), defaults)

    nav.setdefault("navigation_package", "go_router")
    return nav


def apply_navigation_contract(plan: dict[str, Any]) -> dict[str, Any]:
    """Normalize screens, navigation, and user_flows on a full plan dict."""
    updated = copy.deepcopy(plan)
    screens = [
        s for s in updated.get("screens", [])
        if isinstance(s, dict)
    ]
    route_map: dict[str, str] = {}
    if rewrite_root_route_to_home(screens):
        route_map[ROOT_ROUTE] = HOME_ROUTE
        updated["screens"] = screens

    nav = updated.get("navigation")
    if not isinstance(nav, dict):
        nav = {}
    updated["navigation"] = finalize_navigation(screens, nav)

    if route_map:
        _apply_route_map_to_flows(updated.get("user_flows", []), route_map)

    return updated
