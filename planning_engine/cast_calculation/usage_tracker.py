from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import config


def _log_path() -> Path:
    base_dir = Path(__file__).resolve().parent
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / config.COST_LOG_FILENAME


def _read_log(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"calls": [], "totals": _empty_totals()}

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"calls": [], "totals": _empty_totals()}


def _empty_totals() -> dict[str, Any]:
    return {
        "calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "estimated_cost_usd": 0.0,
    }


def _get_attr(obj: Any, name: str, default: int = 0) -> int:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return int(obj.get(name) or default)
    return int(getattr(obj, name, default) or default)


def estimate_tokens(text: str) -> int:
    # Conservative fallback for English/code-like text when provider usage is absent.
    return max(1, len(text) // 4)


def extract_usage(response: Any, prompt: str, output: str) -> dict[str, int]:
    metadata = getattr(response, "usage_metadata", None)
    input_tokens = _get_attr(metadata, "prompt_token_count")
    output_tokens = _get_attr(metadata, "candidates_token_count")
    total_tokens = _get_attr(metadata, "total_token_count")

    if input_tokens <= 0:
        input_tokens = estimate_tokens(prompt)
    if output_tokens <= 0:
        output_tokens = estimate_tokens(output)
    if total_tokens <= 0:
        total_tokens = input_tokens + output_tokens

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def calculate_cost(input_tokens: int, output_tokens: int) -> float:
    input_cost = (input_tokens / 1_000_000) * config.GEMINI_INPUT_COST_PER_1M
    output_cost = (output_tokens / 1_000_000) * config.GEMINI_OUTPUT_COST_PER_1M
    return round(input_cost + output_cost, 8)


def log_llm_call(
    *,
    model: str,
    prompt: str,
    output: str = "",
    response: Any = None,
    success: bool = True,
    error: str = "",
) -> None:
    path = _log_path()
    usage = extract_usage(response, prompt, output)
    cost = calculate_cost(usage["input_tokens"], usage["output_tokens"])

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "success": success,
        "input_tokens": usage["input_tokens"],
        "output_tokens": usage["output_tokens"],
        "total_tokens": usage["total_tokens"],
        "estimated_cost_usd": cost,
        "error": error,
    }

    data = _read_log(path)
    data.setdefault("calls", []).append(entry)

    totals = _empty_totals()
    for call in data["calls"]:
        totals["calls"] += 1
        totals["input_tokens"] += int(call.get("input_tokens", 0))
        totals["output_tokens"] += int(call.get("output_tokens", 0))
        totals["total_tokens"] += int(call.get("total_tokens", 0))
        totals["estimated_cost_usd"] += float(call.get("estimated_cost_usd", 0.0))
    totals["estimated_cost_usd"] = round(totals["estimated_cost_usd"], 8)

    data["totals"] = totals
    data["currency"] = "USD"
    data["pricing_note"] = (
        "Estimated from token counts and GEMINI_*_COST_PER_1M settings."
    )
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

