from __future__ import annotations

import copy
import json
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
            current = current[int(part)]
        else:
            current = current.setdefault(part, {})
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
            parent[index] = value
        elif op == "append":
            parent.append(value)
        elif op == "remove":
            parent.pop(index)
        else:
            raise ValueError(f"Unsupported patch op: {op}")
        return updated

    if op == "set":
        parent[key] = value
    elif op == "append":
        parent.setdefault(key, []).append(value)
    elif op == "remove":
        parent.pop(key, None)
    else:
        raise ValueError(f"Unsupported patch op: {op}")

    return updated


def request_plan_patches(plan: dict[str, Any], instruction: str) -> dict[str, Any]:
    prompt = PLAN_PATCHER.format(
        instruction=instruction,
        plan_json=json.dumps(plan, indent=2),
    )
    result = call_gemini_json(prompt, use_pro=False)
    if not isinstance(result, dict) or "patches" not in result:
        raise RuntimeError("Patch editor did not return a patches object.")
    return result


def edit_plan(plan: dict[str, Any], instruction: str) -> tuple[dict[str, Any], dict[str, Any]]:
    patch_result = request_plan_patches(plan, instruction)
    updated = plan
    for patch in patch_result.get("patches", []):
        updated = apply_patch(updated, patch)

    validation = validate_plan(updated)
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
        except RuntimeError as e:
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
