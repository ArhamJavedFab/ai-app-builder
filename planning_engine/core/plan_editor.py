from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from core.gemini_client import call_gemini_json
from core.prompt_templates import PLAN_PATCHER
from core.summary import print_concise_summary, save_summary
from validation.validator import validate_plan


def load_plan(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_plan(plan: dict[str, Any], path: str | Path) -> None:
    plan_path = Path(path)
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")


def _decode_pointer_part(part: str) -> str:
    return part.replace("~1", "/").replace("~0", "~")


def _resolve_parent(document: Any, pointer: str) -> tuple[Any, str]:
    if not pointer.startswith("/"):
        raise ValueError(f"Invalid JSON pointer: {pointer}")

    parts = [_decode_pointer_part(p) for p in pointer.strip("/").split("/")]
    current = document
    for part in parts[:-1]:
        if isinstance(current, list):
            if part == "-":
                raise ValueError(f"Invalid list parent in JSON pointer: {pointer}")
            current = current[int(part)]
        else:
            if part not in current:
                raise ValueError(f"Patch path does not exist: {pointer}")
            current = current[part]
    return current, parts[-1]


def apply_patch(plan: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    updated = copy.deepcopy(plan)
    op = patch.get("op")
    path = patch.get("path")
    value = patch.get("value")

    parent, key = _resolve_parent(updated, path)
    if isinstance(parent, list):
        index = len(parent) if key == "-" else int(key)
        if op == "set":
            if key == "-" or index >= len(parent):
                raise ValueError(f"Patch index does not exist: {path}")
            parent[index] = value
        elif op == "append":
            parent.append(value)
        elif op == "remove":
            parent.pop(index)
        else:
            raise ValueError(f"Unsupported patch op: {op}")
        return updated

    if op == "set":
        if key not in parent:
            raise ValueError(f"Patch path does not exist: {path}")
        parent[key] = value
    elif op == "append":
        if key not in parent or not isinstance(parent[key], list):
            raise ValueError(f"Patch append target is not a list: {path}")
        parent[key].append(value)
    elif op == "remove":
        parent.pop(key, None)
    else:
        raise ValueError(f"Unsupported patch op: {op}")

    return updated


COLOR_NAMES = {
    "black": "#000000",
    "white": "#FFFFFF",
    "blue": "#2563EB",
    "green": "#16A34A",
    "red": "#DC2626",
    "orange": "#EA580C",
    "yellow": "#FACC15",
    "purple": "#7C3AED",
    "pink": "#DB2777",
    "gray": "#6B7280",
    "grey": "#6B7280",
    "light gray": "#F3F4F6",
    "light grey": "#F3F4F6",
    "dark gray": "#111827",
    "dark grey": "#111827",
    "wheat": "#F5DEB3",
}


def _normalize_hex(value: str) -> str:
    value = value.strip()
    if not value.startswith("#"):
        value = f"#{value}"
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise ValueError(f"Unsupported color value: {value}")
    return value.upper()


def _color_from_text(raw: str) -> str | None:
    text = raw.lower().strip()
    hex_match = re.search(r"#?[0-9a-f]{6}\b", text)
    if hex_match:
        return _normalize_hex(hex_match.group(0))

    for name in sorted(COLOR_NAMES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(name)}\b", text):
            return COLOR_NAMES[name]
    return None


def _local_design_color_patch(instruction: str) -> dict[str, Any] | None:
    text = instruction.lower()
    if "color" not in text and "colour" not in text:
        return None

    field = None
    if "background" in text:
        field = "background_color"
    elif "primary" in text or "main color" in text or "accent" in text:
        field = "primary_color"

    if not field:
        return None

    value_source = instruction
    to_match = re.search(r"\b(?:to|as|=)\s+(.+)$", instruction, flags=re.IGNORECASE)
    if to_match:
        value_source = to_match.group(1)

    color = _color_from_text(value_source)
    if not color:
        return None

    return {
        "summary": f"Updated {field} to {color}.",
        "patches": [
            {
                "op": "set",
                "path": f"/design_system/{field}",
                "value": color,
            }
        ],
    }


def _build_patch_context(plan: dict[str, Any], instruction: str) -> dict[str, Any]:
    text = instruction.lower()
    context: dict[str, Any] = {
        "app_name": plan.get("app_name"),
        "app_type": plan.get("app_type"),
        "available_top_level_paths": sorted(plan.keys()),
    }

    section_keywords = {
        "design_system": ("design", "theme", "color", "colour", "font", "radius", "spacing"),
        "features": ("feature", "mvp", "module", "priority"),
        "screens": ("screen", "page", "widget", "dialog", "sheet", "route"),
        "navigation": ("navigation", "route", "tab", "drawer", "go_router"),
        "backend": ("backend", "api", "endpoint", "auth", "jwt", "payment", "notification"),
        "database_tables": ("database", "table", "field", "schema", "relation", "index"),
        "flutter_architecture": ("architecture", "riverpod", "bloc", "provider", "dependency", "folder"),
    }

    selected = [
        section
        for section, keywords in section_keywords.items()
        if section in plan and any(keyword in text for keyword in keywords)
    ]
    if not selected:
        selected = ["design_system", "features", "screens", "navigation"]

    context["sections"] = {section: plan.get(section) for section in selected}
    context["validation_warnings"] = plan.get("validation_warnings", [])
    return context


def request_plan_patches(plan: dict[str, Any], instruction: str) -> dict[str, Any]:
    local_patch = _local_design_color_patch(instruction)
    if local_patch:
        return local_patch

    patch_context = _build_patch_context(plan, instruction)
    prompt = PLAN_PATCHER.format(
        instruction=instruction,
        plan_context=json.dumps(patch_context, indent=2),
    )
    result = call_gemini_json(prompt, use_pro=False)
    if not isinstance(result, dict) or "patches" not in result:
        raise RuntimeError("Patch editor did not return a patches object.")
    # Normalize any patch paths that mistakenly reference a "sections" wrapper.
    for patch in result.get("patches", []):
        path = patch.get("path", "")
        if path.startswith("/sections"):
            # Remove the leading "/sections" segment to match the actual plan structure.
            patch["path"] = path.replace("/sections", "", 1)
    return result


def edit_plan(plan: dict[str, Any], instruction: str) -> tuple[dict[str, Any], dict[str, Any]]:
    patch_result = request_plan_patches(plan, instruction)
    updated = plan
    for patch in patch_result.get("patches", []):
        updated = apply_patch(updated, patch)

    validation = validate_plan(updated, use_llm=False)
    updated["validation_passed"] = validation["validation_passed"]
    updated["confidence_score"] = validation["confidence_score"]
    updated["missing_info"] = validation["missing_info"]
    updated["assumptions_made"] = validation["assumptions_made"]
    updated["ai_notes"] = validation["ai_notes"]
    updated["validation_warnings"] = validation["validation_warnings"]

    return updated, {
        "patch": patch_result,
        "validation": validation,
    }


def run_chat_editor(path: str | Path, summary_path: str | Path | None = None) -> None:
    plan_path = Path(path)
    plan = load_plan(plan_path)
    print("\n  Chat edit mode. Type a change like: update background color to black")
    print("  Type 'exit' to stop.\n")

    while True:
        instruction = input("  edit> ").strip()
        if not instruction:
            continue
        if instruction.lower() in {"exit", "quit", "q"}:
            break

        try:
            plan, result = edit_plan(plan, instruction)
        except (RuntimeError, ValueError) as e:
            print(f"  Edit failed: {e}")
            print("  Plan was not changed.")
            continue

        save_plan(plan, plan_path)
        if summary_path:
            save_summary(plan, summary_path)
        print(f"  Applied: {result['patch'].get('summary', instruction)}")
        print(f"  Saved: {plan_path}")
        if summary_path:
            print(f"  Summary: {summary_path}")
        print_concise_summary(plan)
        if not plan.get("validation_passed"):
            print("  Warning: edited plan did not pass validation.")
