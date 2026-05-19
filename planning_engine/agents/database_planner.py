# ============================================================
# agents/database_planner.py
# ============================================================

import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.gemini_client import call_gemini_json
from core.prompt_templates import DATABASE_PLANNER
import config


def _enforce_firestore_database(result: dict) -> dict:
    result["database_type"] = "firestore"
    result.setdefault("tables", [])
    result.setdefault(
        "local_cache_strategy",
        "Use Firestore offline persistence for local caching.",
    )
    return result


def plan_database(intent: dict, features: dict, backend: dict) -> dict:
    """
    Stage 7 — Generate full database schema with tables, fields, relations.
    Returns dict with tables list and local cache strategy.
    """
    if config.VERBOSE:
        print("  🗄️   Planning database schema...")

    filled = DATABASE_PLANNER.format(
        intent_json=json.dumps(intent, indent=2),
        features_json=json.dumps(features, indent=2),
        backend_json=json.dumps(backend, indent=2),
    )
    result = _enforce_firestore_database(call_gemini_json(filled, use_pro=False))

    if config.VERBOSE:
        tables = len(result.get("tables", []))
        db     = result.get("database_type", "unknown")
        print(f"      {db} | {tables} tables")

    return result
