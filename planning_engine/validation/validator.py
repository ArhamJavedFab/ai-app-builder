# ============================================================
# validation/validator.py — Final quality gate
# ============================================================

import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.gemini_client import call_gemini_json
from core.prompt_templates import VALIDATION_AGENT
import config


# ── Rule-based checks (fast, no LLM) ─────────────────────────

def _rule_based_checks(plan: dict) -> list[dict]:
    issues = []

    screens  = {s["name"] for s in plan.get("screens", [])}
    routes   = {r["path"] for r in plan.get("navigation", {}).get("routes", [])}
    tab_routes = {t["route"] for t in plan.get("navigation", {}).get("bottom_tabs", [])}
    tables   = {t["name"] for t in plan.get("database_tables", [])}
    features = {
        item["name"]
        for module in plan.get("features", [])
        for item in module.get("items", [])
    }

    # 1. Duplicate screen names
    seen = set()
    for s in plan.get("screens", []):
        if s["name"] in seen:
            issues.append({
                "severity": "critical",
                "category": "screens",
                "issue":    f"Duplicate screen name: {s['name']}",
                "fix":      "Rename one of the duplicate screens.",
            })
        seen.add(s["name"])

    # 2. Bottom tab routes without corresponding route entries
    for tab_route in tab_routes:
        if tab_route not in routes:
            issues.append({
                "severity": "warning",
                "category": "navigation",
                "issue":    f"Bottom tab route '{tab_route}' has no matching route entry.",
                "fix":      f"Add a route entry for '{tab_route}'.",
            })

    # 3. Auth needed but no login screen
    backend = plan.get("backend", {})
    if backend.get("auth_provider") and backend.get("auth_provider") != "none":
        has_login = any(
            "login" in s["name"].lower() or "auth" in s["name"].lower()
            for s in plan.get("screens", [])
        )
        if not has_login:
            issues.append({
                "severity": "critical",
                "category": "screens",
                "issue":    "Auth is configured but no login/auth screen found.",
                "fix":      "Add a LoginScreen or AuthScreen.",
            })

    # 4. Payment feature without payment-related table
    payment_features = [f for f in features if "payment" in f.lower() or "checkout" in f.lower()]
    if payment_features:
        has_payment_table = any("payment" in t.lower() or "transaction" in t.lower() for t in tables)
        if not has_payment_table:
            issues.append({
                "severity": "warning",
                "category": "database",
                "issue":    "Payment features detected but no payments/transactions table found.",
                "fix":      "Add a 'payments' or 'transactions' table.",
            })

    # 5. No error screen
    has_error_screen = any("error" in s["name"].lower() or "404" in s["name"].lower() for s in plan.get("screens", []))
    if not has_error_screen:
        issues.append({
            "severity": "suggestion",
            "category": "screens",
            "issue":    "No error or 404 screen found.",
            "fix":      "Add an ErrorScreen for unexpected states.",
        })

    # 6. Realtime but no push table
    if backend.get("realtime") and not backend.get("push_provider"):
        issues.append({
            "severity": "suggestion",
            "category": "backend",
            "issue":    "Realtime is enabled but no push notification provider is set.",
            "fix":      "Consider adding FCM or OneSignal for push notifications.",
        })

    return issues


def validate_plan(plan: dict) -> dict:
    """
    Runs rule-based checks + LLM validation.
    Returns a merged validation result dict.
    """
    if config.VERBOSE:
        print("  ✅  Validating plan (Pro model)...")

    # Rule-based first
    rule_issues = _rule_based_checks(plan)

    # LLM validation
    filled = VALIDATION_AGENT.format(plan_json=json.dumps(plan, indent=2))
    llm_result = call_gemini_json(filled, use_pro=True)

    # Merge
    all_errors = rule_issues + llm_result.get("errors", [])

    critical_count = sum(1 for e in all_errors if e.get("severity") == "critical")
    warning_count  = sum(1 for e in all_errors if e.get("severity") == "warning")

    passed = critical_count == 0

    if config.VERBOSE:
        status = "✅ PASSED" if passed else "❌ FAILED"
        score  = llm_result.get("confidence_score", 0)
        print(f"      {status} | {critical_count} critical | {warning_count} warnings | confidence: {score:.0%}")

        for e in all_errors:
            icon = "🔴" if e["severity"] == "critical" else ("🟡" if e["severity"] == "warning" else "💡")
            print(f"         {icon}  [{e['category']}] {e['issue']}")

    return {
        "validation_passed":  passed,
        "confidence_score":   llm_result.get("confidence_score", 0.0),
        "errors":             all_errors,
        "missing_info":       llm_result.get("missing_info", []),
        "assumptions_made":   llm_result.get("assumptions_made", []),
        "ai_notes":           llm_result.get("ai_notes", []),
        "validation_warnings": [e["issue"] for e in all_errors if e["severity"] == "warning"],
    }
