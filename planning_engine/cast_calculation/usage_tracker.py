from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import config

_current_run_id: str | None = None


def _log_path() -> Path:
    configured_dir = Path(config.COST_LOG_DIR)
    if configured_dir.is_absolute():
        base_dir = configured_dir
    else:
        base_dir = Path(__file__).resolve().parents[1] / configured_dir
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / config.COST_LOG_FILENAME


def _read_log(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _empty_log()

    try:
        return _normalize_log(json.loads(path.read_text(encoding="utf-8")))
    except json.JSONDecodeError:
        return _empty_log()


def _empty_log() -> dict[str, Any]:
    return {
        "runs": [],
        "currency": "USD",
        "pricing_note": (
            "Estimated from token counts and GEMINI_*_COST_PER_1M settings."
        ),
        "all_runs_total": _empty_totals(),
    }


def _empty_totals() -> dict[str, Any]:
    return {
        "calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "estimated_cost_usd": 0.0,
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_run(label: str = "planning_run", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "run_id": f"run_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}",
        "label": label,
        "started_at": _utc_now(),
        "ended_at": None,
        "metadata": metadata or {},
        "calls": [],
        "totals": _empty_totals(),
    }


def _calculate_totals(calls: list[dict[str, Any]]) -> dict[str, Any]:
    totals = _empty_totals()
    for call in calls:
        totals["calls"] += 1
        totals["input_tokens"] += int(call.get("input_tokens", 0))
        totals["output_tokens"] += int(call.get("output_tokens", 0))
        totals["total_tokens"] += int(call.get("total_tokens", 0))
        totals["estimated_cost_usd"] += float(call.get("estimated_cost_usd", 0.0))
    totals["estimated_cost_usd"] = round(totals["estimated_cost_usd"], 8)
    return totals


def _recalculate_all_totals(data: dict[str, Any]) -> None:
    all_totals = _empty_totals()
    for run in data.get("runs", []):
        run["totals"] = _calculate_totals(run.get("calls", []))
        totals = run["totals"]
        all_totals["calls"] += totals["calls"]
        all_totals["input_tokens"] += totals["input_tokens"]
        all_totals["output_tokens"] += totals["output_tokens"]
        all_totals["total_tokens"] += totals["total_tokens"]
        all_totals["estimated_cost_usd"] += totals["estimated_cost_usd"]
    all_totals["estimated_cost_usd"] = round(all_totals["estimated_cost_usd"], 8)
    data["all_runs_total"] = all_totals


def _normalize_log(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return _empty_log()

    if "runs" in data and isinstance(data["runs"], list):
        normalized = {
            "runs": data["runs"],
            "all_runs_total": data.get("all_runs_total", _empty_totals()),
            "currency": data.get("currency", "USD"),
            "pricing_note": data.get(
                "pricing_note",
                "Estimated from token counts and GEMINI_*_COST_PER_1M settings.",
            ),
        }
        _recalculate_all_totals(normalized)
        return normalized

    legacy_calls = data.get("calls", [])
    if isinstance(legacy_calls, list) and legacy_calls:
        legacy_run = _new_run("legacy_import", {"source": "pre-run-grouped log"})
        legacy_run["run_id"] = "legacy_import"
        legacy_run["started_at"] = legacy_calls[0].get("timestamp") or legacy_run["started_at"]
        legacy_run["ended_at"] = legacy_calls[-1].get("timestamp") or legacy_run["started_at"]
        legacy_run["calls"] = legacy_calls
        normalized = _empty_log()
        normalized["runs"] = [legacy_run]
        _recalculate_all_totals(normalized)
        return normalized

    return _empty_log()


def _write_log(path: Path, data: dict[str, Any]) -> None:
    data["currency"] = "USD"
    data["pricing_note"] = (
        "Estimated from token counts and GEMINI_*_COST_PER_1M settings."
    )
    _recalculate_all_totals(data)
    ordered_data = {
        "runs": data.get("runs", []),
        "currency": data["currency"],
        "pricing_note": data["pricing_note"],
        "all_runs_total": data["all_runs_total"],
    }
    path.write_text(json.dumps(ordered_data, indent=2), encoding="utf-8")


def _find_run(data: dict[str, Any], run_id: str) -> dict[str, Any] | None:
    for run in data.get("runs", []):
        if run.get("run_id") == run_id:
            return run
    return None


def start_usage_run(
    label: str = "planning_run",
    metadata: dict[str, Any] | None = None,
) -> str:
    global _current_run_id

    path = _log_path()
    data = _read_log(path)
    run = _new_run(label, metadata)
    data.setdefault("runs", []).append(run)
    _current_run_id = run["run_id"]
    _write_log(path, data)
    return _current_run_id


def finish_usage_run(run_id: str | None = None) -> dict[str, Any]:
    global _current_run_id

    path = _log_path()
    data = _read_log(path)
    active_run_id = run_id or _current_run_id
    if not active_run_id:
        return {"run": None, "all_runs_total": data.get("all_runs_total", _empty_totals())}

    run = _find_run(data, active_run_id)
    if run is None:
        return {"run": None, "all_runs_total": data.get("all_runs_total", _empty_totals())}

    run["ended_at"] = _utc_now()
    _write_log(path, data)
    if active_run_id == _current_run_id:
        _current_run_id = None
    return {"run": run, "all_runs_total": data["all_runs_total"]}


def format_cost_summary(run_result: dict[str, Any]) -> str:
    run = run_result.get("run")
    all_runs_total = run_result.get("all_runs_total", _empty_totals())
    run_totals = (run or {}).get("totals", _empty_totals())
    return (
        f"Run cost: ${run_totals['estimated_cost_usd']:.6f} "
        f"({run_totals['calls']} LLM calls, {run_totals['total_tokens']} tokens)\n"
        f"All runs total: ${all_runs_total['estimated_cost_usd']:.6f} "
        f"({all_runs_total['calls']} LLM calls, {all_runs_total['total_tokens']} tokens)"
    )


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
    global _current_run_id

    path = _log_path()
    usage = extract_usage(response, prompt, output)
    cost = calculate_cost(usage["input_tokens"], usage["output_tokens"])

    entry = {
        "timestamp": _utc_now(),
        "model": model,
        "success": success,
        "input_characters": len(prompt),
        "output_characters": len(output),
        "input_tokens": usage["input_tokens"],
        "output_tokens": usage["output_tokens"],
        "total_tokens": usage["total_tokens"],
        "estimated_cost_usd": cost,
        "error": error,
    }

    data = _read_log(path)
    if not _current_run_id:
        _current_run_id = start_usage_run("implicit_run", {"source": "log_llm_call"})
        data = _read_log(path)

    run = _find_run(data, _current_run_id)
    if run is None:
        run = _new_run("implicit_run", {"source": "missing active run"})
        run["run_id"] = _current_run_id
        data.setdefault("runs", []).append(run)

    entry["run_id"] = run["run_id"]
    run.setdefault("calls", []).append(entry)
    _write_log(path, data)
