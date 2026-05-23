# ============================================================
# agents/flow_planner.py
# ============================================================

import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.gemini_client import call_gemini_json
from core.prompt_loader import load_prompt_template
import config

FLOW_PLANNER = load_prompt_template("flow_planner.md")

_SKIP_SCREEN_NAMES = frozenset({"splashscreen", "errorscreen"})


def _known_routes(screens: list) -> set[str]:
    routes: set[str] = set()
    for screen in screens:
        if isinstance(screen, dict):
            route = (screen.get("route") or "").strip()
            if route:
                routes.add(route)
    return routes


def _filter_flow_steps(steps: list, valid_routes: set[str]) -> list[str]:
    out: list[str] = []
    for step in steps:
        if not isinstance(step, str):
            continue
        path = step.strip()
        if not path.startswith("/"):
            continue
        if path in valid_routes:
            out.append(path)
    return out


def _fallback_user_flows(screens: list, navigation: dict) -> list[dict]:
    """Rule-based flows when the LLM call fails or returns nothing usable."""
    valid = _known_routes(screens)
    if not valid:
        return []

    by_route = {
        (s.get("route") or ""): s.get("name", "")
        for s in screens
        if isinstance(s, dict) and s.get("route")
    }
    flows: list[dict] = []

    onboarding_chain = [
        r
        for r in ("/splash", "/onboarding", "/permissions", "/login", "/signup")
        if r in valid
    ]
    home_candidates = [
        r
        for r in valid
        if r not in {"/splash", "/onboarding", "/permissions", "/login", "/signup", "/error"}
        and by_route.get(r, "").lower() not in _SKIP_SCREEN_NAMES
    ]
    home = "/" if "/" in valid else (home_candidates[0] if home_candidates else "")

    if len(onboarding_chain) >= 2 or (onboarding_chain and home):
        steps = list(onboarding_chain)
        if home and home not in steps:
            steps.append(home)
        if len(steps) >= 2:
            flows.append({
                "name": "First launch",
                "trigger": "User opens the app for the first time",
                "priority": "mvp",
                "steps": steps,
                "description": "Onboarding and permission setup before reaching the main experience.",
            })

    detail_routes = sorted(r for r in valid if ":id" in r or "/detail" in r)
    if home and detail_routes:
        for route in detail_routes[:2]:
            name = by_route.get(route, route)
            flows.append({
                "name": f"View {name.replace('Screen', '').strip() or 'item'}",
                "trigger": f"User selects an item on {home}",
                "priority": "post_mvp" if "share" in route.lower() or "delete" in route.lower() else "mvp",
                "steps": [home, route],
                "description": f"Navigate from home to {route}.",
            })

    guest = navigation.get("guest_routes") if isinstance(navigation, dict) else None
    if isinstance(guest, list) and home:
        guest_steps = [r for r in guest if isinstance(r, str) and r in valid and r != home]
        if guest_steps:
            flows.append({
                "name": "Guest browsing",
                "trigger": "User uses the app without signing in",
                "priority": "mvp",
                "steps": [home] + guest_steps[:3],
                "description": "Primary paths available without authentication.",
            })

    if not flows and home:
        flows.append({
            "name": "Main usage",
            "trigger": "User opens the app",
            "priority": "mvp",
            "steps": [home],
            "description": "Core screen for the app.",
        })

    return flows


def plan_user_flows(intent: dict, screens_data: dict, navigation: dict) -> dict:
    """
    Stage 5b — Derive user flows from screens and navigation.
    Returns {user_flows: [...]}.
    """
    screens = screens_data.get("screens", []) if isinstance(screens_data, dict) else []
    valid_routes = _known_routes(screens)

    if config.VERBOSE:
        print("  >>  Planning user flows...")

    result: dict = {"user_flows": []}
    try:
        prompt = FLOW_PLANNER.format(
            intent_json=json.dumps(intent, indent=2),
            screens_json=json.dumps(screens_data, indent=2),
            navigation_json=json.dumps(navigation, indent=2),
        )
        result = call_gemini_json(prompt, use_pro=False)
    except Exception as exc:
        if config.VERBOSE:
            print(f"      WARN  Flow planner LLM failed: {exc}")

    flows = result.get("user_flows", []) if isinstance(result, dict) else []
    cleaned: list[dict] = []
    for flow in flows:
        if not isinstance(flow, dict):
            continue
        steps = _filter_flow_steps(flow.get("steps", []), valid_routes)
        if len(steps) < 1:
            continue
        cleaned.append({
            "name": flow.get("name", "Unnamed flow"),
            "trigger": flow.get("trigger", ""),
            "priority": flow.get("priority", "mvp"),
            "steps": steps,
            "description": flow.get("description", ""),
        })

    if not cleaned:
        cleaned = _fallback_user_flows(screens, navigation)

    if config.VERBOSE:
        print(f"      {len(cleaned)} user flow(s)")

    return {"user_flows": cleaned}
