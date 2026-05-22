# ============================================================
# core/plan_ids.py — Stable IDs for master plan entities
# ============================================================

from __future__ import annotations

import copy
import re
import uuid
from datetime import datetime, timezone
from typing import Any

PLAN_VERSION = "1.1"

PREFIX_SCREEN = "scr_"
PREFIX_MODULE = "mod_"
PREFIX_FEATURE = "feat_"
PREFIX_ROUTE = "route_"
PREFIX_TAB = "tab_"
PREFIX_TABLE = "tbl_"
PREFIX_FIELD = "fld_"
PREFIX_WIDGET = "wgt_"
PREFIX_FLOW = "flow_"
PREFIX_DEP = "dep_"
PREFIX_EXT = "ext_"

# Collections patchable by stable id (top-level list on plan dict).
ID_COLLECTIONS = frozenset({
    "screens",
    "database_tables",
    "user_flows",
    "flutter_dependencies",
    "dev_dependencies",
    "analytics_events",
})

NESTED_ID_COLLECTIONS: dict[str, tuple[str, str]] = {
    # parent_key -> (list_key, child_prefix)
    "features": ("items", PREFIX_FEATURE),
}


def new_id(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


def _slug(value: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (value or "").lower()).strip("_")
    return slug[:max_len] if slug else "item"


def _ensure_id(
    item: dict[str, Any],
    prefix: str,
    used: set[str],
    *,
    seed: str | None = None,
) -> str:
    existing = (item.get("id") or "").strip()
    if existing and existing not in used:
        used.add(existing)
        return existing
    if seed:
        candidate = f"{prefix}{_slug(seed)}"
        if candidate not in used:
            used.add(candidate)
            item["id"] = candidate
            return candidate
    while True:
        candidate = new_id(prefix)
        if candidate not in used:
            used.add(candidate)
            item["id"] = candidate
            return candidate


def find_index_by_id(items: list[dict[str, Any]], entity_id: str) -> int | None:
    for i, item in enumerate(items):
        if isinstance(item, dict) and item.get("id") == entity_id:
            return i
    return None


def find_by_id(items: list[dict[str, Any]], entity_id: str) -> dict[str, Any] | None:
    idx = find_index_by_id(items, entity_id)
    if idx is None:
        return None
    return items[idx]


def build_id_index(plan: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    """Compact index for LLM patch context."""
    index: dict[str, list[dict[str, str]]] = {}

    for screen in plan.get("screens", []):
        if not isinstance(screen, dict):
            continue
        index.setdefault("screens", []).append({
            "id": screen.get("id", ""),
            "name": screen.get("name", ""),
            "route": screen.get("route", ""),
        })

    for mod in plan.get("features", []):
        if not isinstance(mod, dict):
            continue
        index.setdefault("feature_modules", []).append({
            "id": mod.get("id", ""),
            "module": mod.get("module", ""),
        })
        for item in mod.get("items", []):
            if not isinstance(item, dict):
                continue
            index.setdefault("feature_items", []).append({
                "id": item.get("id", ""),
                "name": item.get("name", ""),
                "module_id": mod.get("id", ""),
            })

    nav = plan.get("navigation") or {}
    for route in nav.get("routes", []):
        if not isinstance(route, dict):
            continue
        index.setdefault("navigation_routes", []).append({
            "id": route.get("id", ""),
            "path": route.get("path", ""),
            "screen_id": route.get("screen_id", ""),
            "screen": route.get("screen", ""),
        })

    for table in plan.get("database_tables", []):
        if not isinstance(table, dict):
            continue
        index.setdefault("database_tables", []).append({
            "id": table.get("id", ""),
            "name": table.get("name", ""),
        })

    return index


def _map_by_key(items: list[dict[str, Any]], key: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        k = item.get(key)
        eid = item.get("id")
        if k and eid:
            out[str(k)] = eid
    return out


def _link_screen_refs(plan: dict[str, Any], screen_by_name: dict[str, str], screen_by_route: dict[str, str]) -> None:
    nav = plan.get("navigation")
    if not isinstance(nav, dict):
        return

    for route in nav.get("routes", []):
        if not isinstance(route, dict):
            continue
        screen_name = route.get("screen", "")
        path = route.get("path", "")
        if not route.get("screen_id"):
            route["screen_id"] = screen_by_name.get(screen_name) or screen_by_route.get(path, "")

    for tab in nav.get("bottom_tabs", []):
        if not isinstance(tab, dict):
            continue
        path = tab.get("route", "")
        if not tab.get("route_id"):
            for r in nav.get("routes", []):
                if isinstance(r, dict) and r.get("path") == path:
                    tab["route_id"] = r.get("id", "")
                    break


def _link_feature_refs(plan: dict[str, Any], feat_by_name: dict[str, str]) -> None:
    mvp_ids: list[str] = []
    post_ids: list[str] = []

    for name in plan.get("mvp_features", []):
        if isinstance(name, str) and name in feat_by_name:
            mvp_ids.append(feat_by_name[name])
    for name in plan.get("post_mvp_features", []):
        if isinstance(name, str) and name in feat_by_name:
            post_ids.append(feat_by_name[name])

    if mvp_ids:
        plan["mvp_feature_ids"] = mvp_ids
    if post_ids:
        plan["post_mvp_feature_ids"] = post_ids

    for mod in plan.get("features", []):
        if not isinstance(mod, dict):
            continue
        for item in mod.get("items", []):
            if not isinstance(item, dict):
                continue
            names = item.get("depends_on") or []
            if names and not item.get("depends_on_ids"):
                item["depends_on_ids"] = [
                    feat_by_name[n] for n in names if isinstance(n, str) and n in feat_by_name
                ]


def _assign_reusable_components(plan: dict[str, Any], used: set[str], screen_by_name: dict[str, str]) -> None:
    components = plan.get("reusable_components")
    if not isinstance(components, list):
        return
    for comp in components:
        if not isinstance(comp, dict):
            continue
        _ensure_id(comp, PREFIX_WIDGET, used, seed=comp.get("name"))
        used_in = comp.get("used_in") or []
        if used_in and not comp.get("used_in_screen_ids"):
            comp["used_in_screen_ids"] = [
                screen_by_name[n] for n in used_in if isinstance(n, str) and n in screen_by_name
            ]


def normalize_plan_ids(plan: dict[str, Any], *, touch_updated_at: bool = True) -> dict[str, Any]:
    """
    Ensure every addressable plan entity has a stable id and cross-refs use ids.
    Safe to run repeatedly (idempotent for existing valid ids).
    """
    normalized = copy.deepcopy(plan)
    used: set[str] = set()

    if not normalized.get("plan_version"):
        normalized["plan_version"] = PLAN_VERSION
    if not normalized.get("project_id"):
        normalized["project_id"] = new_id("prj_")

    # ── Screens ───────────────────────────────────────────────
    for screen in normalized.get("screens", []):
        if not isinstance(screen, dict):
            continue
        seed = screen.get("name") or screen.get("route")
        _ensure_id(screen, PREFIX_SCREEN, used, seed=seed)

    screen_by_name = _map_by_key(normalized.get("screens", []), "name")
    screen_by_route = _map_by_key(normalized.get("screens", []), "route")

    # ── Feature modules + items ─────────────────────────────
    feat_by_name: dict[str, str] = {}
    for mod in normalized.get("features", []):
        if not isinstance(mod, dict):
            continue
        mod_seed = mod.get("module", "")
        _ensure_id(mod, PREFIX_MODULE, used, seed=mod_seed)
        for item in mod.get("items", []):
            if not isinstance(item, dict):
                continue
            name = item.get("name", "")
            _ensure_id(item, PREFIX_FEATURE, used, seed=name)
            if name:
                feat_by_name[name] = item["id"]

    _link_feature_refs(normalized, feat_by_name)

    # ── Navigation ──────────────────────────────────────────
    nav = normalized.setdefault("navigation", {})
    if not isinstance(nav, dict):
        nav = {}
        normalized["navigation"] = nav

    for route in nav.get("routes", []):
        if not isinstance(route, dict):
            continue
        seed = route.get("path") or route.get("screen")
        _ensure_id(route, PREFIX_ROUTE, used, seed=seed)
        if not route.get("screen_id"):
            route["screen_id"] = screen_by_name.get(route.get("screen", ""), "")

    for tab in nav.get("bottom_tabs", []):
        if not isinstance(tab, dict):
            continue
        _ensure_id(tab, PREFIX_TAB, used, seed=tab.get("label") or tab.get("route"))

    _link_screen_refs(normalized, screen_by_name, screen_by_route)

    # ── Database ──────────────────────────────────────────────
    table_by_name: dict[str, str] = {}
    for table in normalized.get("database_tables", []):
        if not isinstance(table, dict):
            continue
        tname = table.get("name", "")
        _ensure_id(table, PREFIX_TABLE, used, seed=tname)
        if tname:
            table_by_name[tname.lower()] = table["id"]
        for field in table.get("fields", []):
            if not isinstance(field, dict):
                continue
            _ensure_id(field, PREFIX_FIELD, used, seed=field.get("name"))
        for rel in table.get("relations", []):
            if not isinstance(rel, dict):
                continue
            ref_table = (rel.get("table") or "").lower()
            if ref_table and not rel.get("table_id"):
                rel["table_id"] = table_by_name.get(ref_table, "")

    # ── User flows ────────────────────────────────────────────
    for flow in normalized.get("user_flows", []):
        if not isinstance(flow, dict):
            continue
        _ensure_id(flow, PREFIX_FLOW, used, seed=flow.get("name"))

    # ── Dependencies & third-party ────────────────────────────
    for dep in normalized.get("flutter_dependencies", []):
        if isinstance(dep, dict):
            _ensure_id(dep, PREFIX_DEP, used, seed=dep.get("package"))
    for dep in normalized.get("dev_dependencies", []):
        if isinstance(dep, dict):
            _ensure_id(dep, PREFIX_DEP, used, seed=dep.get("package"))

    backend = normalized.get("backend")
    if isinstance(backend, dict):
        for api in backend.get("third_party_apis", []):
            if isinstance(api, dict):
                _ensure_id(api, PREFIX_EXT, used, seed=api.get("name"))

    _assign_reusable_components(normalized, used, screen_by_name)

    if touch_updated_at:
        normalized["updated_at"] = datetime.now(timezone.utc).isoformat()

    return normalized


def resolve_patch_path(plan: dict[str, Any], patch: dict[str, Any]) -> str:
    """
    Convert id-based patch target to JSON Pointer path.
    Supports legacy patches that already include "path".
    """
    if patch.get("path"):
        return patch["path"]

    target = patch.get("target")
    if not isinstance(target, dict):
        raise ValueError("Patch must include 'path' or 'target' with collection and id.")

    collection = target.get("collection", "")
    entity_id = target.get("id", "")
    field = patch.get("field", "")

    if collection not in ID_COLLECTIONS and collection not in NESTED_ID_COLLECTIONS:
        raise ValueError(f"Unsupported patch collection: {collection}")

    if collection in NESTED_ID_COLLECTIONS:
        list_key, _ = NESTED_ID_COLLECTIONS[collection]
        idx = None
        child_idx = None
        for i, parent in enumerate(plan.get(collection, [])):
            if not isinstance(parent, dict) or parent.get("id") != entity_id:
                continue
            idx = i
            child_id = target.get("child_id")
            if child_id:
                child_idx = find_index_by_id(parent.get(list_key, []), child_id)
            break
        if idx is None:
            raise ValueError(f"Entity not found: {collection} id={entity_id}")
        if target.get("child_id") is not None:
            if child_idx is None:
                raise ValueError(f"Child not found in {collection}: child_id={target.get('child_id')}")
            base = f"/{collection}/{idx}/{list_key}/{child_idx}"
        else:
            base = f"/{collection}/{idx}"
    else:
        idx = find_index_by_id(plan.get(collection, []), entity_id)
        if idx is None:
            raise ValueError(f"Entity not found: {collection} id={entity_id}")
        base = f"/{collection}/{idx}"

    if patch.get("op") in ("append", "remove") and not field:
        if patch.get("op") == "append":
            return f"/{collection}"
        return base

    if field:
        if not field.startswith("/"):
            field = f"/{field}"
        return f"{base}{field}"
    rel = patch.get("path_suffix", "")
    if rel:
        if not rel.startswith("/"):
            rel = f"/{rel}"
        return f"{base}{rel}"
    raise ValueError("Id-based patch requires 'field', 'path_suffix', or op 'append'.")


def prepare_patch_for_apply(plan: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Resolve target-based patches; assign id on append of new dict items."""
    resolved = dict(patch)
    if patch.get("target") and not patch.get("path"):
        resolved["path"] = resolve_patch_path(plan, patch)
    op = resolved.get("op")
    value = resolved.get("value")
    if op == "append" and isinstance(value, dict) and not value.get("id"):
        collection = (patch.get("target") or {}).get("collection", "")
        prefix_map = {
            "screens": PREFIX_SCREEN,
            "database_tables": PREFIX_TABLE,
            "user_flows": PREFIX_FLOW,
            "flutter_dependencies": PREFIX_DEP,
            "dev_dependencies": PREFIX_DEP,
        }
        prefix = prefix_map.get(collection, "ent_")
        used = _collect_all_ids(plan)
        seed = value.get("name") or value.get("route") or value.get("module")
        _ensure_id(value, prefix, used, seed=seed)
    return resolved


def _collect_all_ids(plan: dict[str, Any]) -> set[str]:
    used: set[str] = set()
    for key in ("project_id",):
        if plan.get(key):
            used.add(plan[key])
    for screen in plan.get("screens", []):
        if isinstance(screen, dict) and screen.get("id"):
            used.add(screen["id"])
    for mod in plan.get("features", []):
        if isinstance(mod, dict):
            if mod.get("id"):
                used.add(mod["id"])
            for item in mod.get("items", []):
                if isinstance(item, dict) and item.get("id"):
                    used.add(item["id"])
    nav = plan.get("navigation") or {}
    for route in nav.get("routes", []):
        if isinstance(route, dict) and route.get("id"):
            used.add(route["id"])
    for tab in nav.get("bottom_tabs", []):
        if isinstance(tab, dict) and tab.get("id"):
            used.add(tab["id"])
    for table in plan.get("database_tables", []):
        if isinstance(table, dict) and table.get("id"):
            used.add(table["id"])
    return used
