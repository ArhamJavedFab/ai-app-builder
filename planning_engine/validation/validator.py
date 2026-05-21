# ============================================================
# validation/validator.py — Final quality gate
#
# TWO-LAYER VALIDATION:
#   Layer 1 — Rule-based (instant, no LLM cost)
#     Deterministic checks that catch structural errors the LLM
#     sometimes misses or inconsistently flags.
#
#   Layer 2 — LLM-based (Gemini Pro)
#     Catches semantic and cross-section inconsistencies that
#     rules can't easily express.
#
# The results are merged and de-duplicated before being returned.
# ============================================================

import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.gemini_client import call_gemini_json
from core.prompt_templates import VALIDATION_AGENT
import config


# ── Helpers ───────────────────────────────────────────────────

def _issue(severity: str, category: str, issue: str, fix: str) -> dict:
    return {"severity": severity, "category": category, "issue": issue, "fix": fix}


# ── Rule-based checks ─────────────────────────────────────────

def _rule_based_checks(plan: dict) -> list[dict]:
    issues = []

    screens        = plan.get("screens", [])
    screen_names   = [s.get("name", "") for s in screens]
    screen_routes  = {s.get("route", "") for s in screens}
    nav            = plan.get("navigation", {})
    routes         = {r.get("path", "") for r in nav.get("routes", [])}
    tab_routes     = {t.get("route", "") for t in nav.get("bottom_tabs", [])}
    backend        = plan.get("backend", {})
    backend_type   = backend.get("backend_type", "")
    tables         = {t.get("name", "").lower() for t in plan.get("database_tables", [])}
    arch           = plan.get("flutter_architecture", {})
    design         = plan.get("design_system", {})

    # Collect all endpoint paths for cross-referencing
    endpoints      = {e.get("path", "") for e in backend.get("api_endpoints", [])}

    if backend_type and backend_type != "firebase":
        issues.append(_issue(
            "critical", "backend",
            f"backend_type is '{backend_type}', but this planner must use Firebase.",
            "Set backend.backend_type to 'firebase'.",
        ))
    if backend.get("auth_provider") not in ("", "firebase_auth"):
        issues.append(_issue(
            "critical", "backend",
            f"auth_provider is '{backend.get('auth_provider')}', but this planner must use Firebase Auth.",
            "Set backend.auth_provider to 'firebase_auth'.",
        ))
    if backend.get("api_endpoints"):
        issues.append(_issue(
            "critical", "backend",
            "backend.api_endpoints is not empty, but Firebase plans must use SDK calls instead of REST endpoints.",
            "Set backend.api_endpoints to [].",
        ))
    if arch.get("network_layer") not in ("", "firebase_sdk"):
        issues.append(_issue(
            "critical", "architecture",
            f"network_layer is '{arch.get('network_layer')}', but Firebase SDKs must be used.",
            "Set flutter_architecture.network_layer to 'firebase_sdk'.",
        ))
    if arch.get("local_database") not in ("", "firestore_offline_cache"):
        issues.append(_issue(
            "critical", "architecture",
            f"local_database is '{arch.get('local_database')}', but Firestore offline cache must be used.",
            "Set flutter_architecture.local_database to 'firestore_offline_cache'.",
        ))

    # ── 1. Duplicate screen names ─────────────────────────────
    seen = {}
    for name in screen_names:
        seen[name] = seen.get(name, 0) + 1
    for name, count in seen.items():
        if count > 1:
            issues.append(_issue(
                "critical", "screens",
                f"Duplicate screen name: '{name}' appears {count} times.",
                f"Rename one of the '{name}' screens to make all names unique.",
            ))

    # ── 2. Bottom-tab routes not in routes array ──────────────
    for tab_route in tab_routes:
        if tab_route and tab_route not in routes:
            issues.append(_issue(
                "critical", "navigation",
                f"Bottom tab route '{tab_route}' is not defined in the routes array.",
                f"Add a route entry for '{tab_route}' in navigation.routes.",
            ))

    # ── 3. Auth configured but no login screen ────────────────
    auth_provider = backend.get("auth_provider", "")
    if auth_provider and auth_provider not in ("none", ""):
        has_login = any(
            "login" in n.lower() or "signin" in n.lower() or "auth" in n.lower()
            for n in screen_names
        )
        if not has_login:
            issues.append(_issue(
                "critical", "screens",
                f"Auth provider is '{auth_provider}' but no LoginScreen/SigninScreen found.",
                "Add a LoginScreen with route /login to the screens array.",
            ))

    # ── 4. Payment gateway needed but no payments table ───────
    # Only flag this when needs_payment_gateway is explicitly true.
    # COD (cash on delivery) does NOT need a payments table.
    if backend.get("needs_payment_gateway") is True:
        has_payment_table = any(
            t in tables for t in ("payments", "transactions", "payment_records")
        )
        if not has_payment_table:
            issues.append(_issue(
                "warning", "database",
                "needs_payment_gateway is true but no payments/transactions table exists.",
                "Add a 'payments' table, or set needs_payment_gateway to false if using COD.",
            ))

    # ── 5. Public endpoints with non-empty roles ──────────────
    for ep in backend.get("api_endpoints", []):
        if ep.get("auth_required") is False and ep.get("roles"):
            issues.append(_issue(
                "warning", "backend",
                f"Endpoint {ep.get('method','')} {ep.get('path','')} has auth_required: false "
                f"but also lists roles: {ep.get('roles')}. Roles have no effect on public endpoints.",
                f"Set roles: [] for {ep.get('method','')} {ep.get('path','')}.",
            ))

    # ── 6. Missing profile endpoint ───────────────────────────
    has_profile_screen = any("profile" in n.lower() for n in screen_names)
    if has_profile_screen and backend_type != "firebase":
        has_profile_endpoint = any(
            "profile" in p.lower() or "user" in p.lower()
            for p in endpoints
        )
        if not has_profile_endpoint:
            issues.append(_issue(
                "warning", "backend",
                "ProfileScreen exists but no user/profile endpoint found in api_endpoints.",
                "Use Firebase Auth plus a users Firestore collection for profile data.",
            ))

    # ── 7. Screen api_calls without matching endpoint ─────────
    for screen in ([] if backend_type == "firebase" else screens):
        for call in screen.get("api_calls", []):
            # Extract just the path part (e.g. "GET /api/v1/products" → "/api/v1/products")
            parts = call.strip().split()
            path  = parts[-1] if parts else call
            if path and path not in endpoints:
                issues.append(_issue(
                    "warning", "backend",
                    f"Screen '{screen.get('name','')}' has api_call '{call}' "
                    f"but '{path}' is not in backend.api_endpoints.",
                    f"Replace '{call}' with a Firebase SDK action and keep backend.api_endpoints empty.",
                ))

    # ── 8. Cart strategy vs backend mismatch ─────────────────
    cart_strategy = arch.get("cart_strategy", "")
    has_cart_endpoint = any("cart" in p.lower() for p in endpoints)
    has_cart_table    = any("cart" in t for t in tables)

    if cart_strategy == "local" and has_cart_endpoint:
        issues.append(_issue(
            "warning", "architecture",
            "cart_strategy is 'local' but backend has cart API endpoints. This is contradictory.",
            "Either set cart_strategy to 'server' or remove the cart endpoints from the backend.",
        ))
    if cart_strategy == "server" and has_cart_table and not has_cart_endpoint:
        issues.append(_issue(
            "warning", "architecture",
            "cart_strategy is 'server' and a cart table exists, but no cart endpoint is defined.",
            "Set cart_strategy to 'firestore' and use a cart/cart_items Firestore collection.",
        ))

    # ── 9. Design color contrast ──────────────────────────────
    primary    = design.get("primary_color", "")
    background = design.get("background_color", "")
    if primary and background and primary.lstrip("#").lower() == background.lstrip("#").lower():
        issues.append(_issue(
            "warning", "design",
            f"primary_color ({primary}) and background_color ({background}) are identical.",
            "Use a contrasting background color.",
        ))

    # ── 10. Missing ErrorScreen ───────────────────────────────
    has_error = any("error" in n.lower() or "404" in n for n in screen_names)
    if not has_error:
        issues.append(_issue(
            "suggestion", "screens",
            "No ErrorScreen or 404 screen found.",
            "Add an ErrorScreen with route /error for unexpected states.",
        ))

    return issues


# ── De-duplication ────────────────────────────────────────────

def _dedup_errors(errors: list[dict]) -> list[dict]:
    """
    Remove semantically duplicate issues. If both rule-based and LLM
    catch the same problem (e.g. missing payments table), keep only the
    most specific one (the rule-based version).
    """
    seen_keys   = set()
    deduplicated = []
    for e in errors:
        # Key on (category, first 60 chars of issue) to catch near-duplicates
        key = (e.get("category", ""), e.get("issue", "")[:60].lower())
        if key not in seen_keys:
            seen_keys.add(key)
            deduplicated.append(e)
    return deduplicated


# ── Public interface ──────────────────────────────────────────

def validate_plan(plan: dict, use_llm: bool = True) -> dict:
    """
    Runs rule-based checks + LLM validation.
    Returns a merged, de-duplicated validation result dict.
    """
    if config.VERBOSE:
        mode = "Pro model" if use_llm else "rule-based only"
        print(f"  ✅  Validating plan ({mode})...")

    # Layer 1: deterministic rules (no LLM)
    rule_issues = _rule_based_checks(plan)

    # Layer 2: LLM semantic validation
    if use_llm:
        try:
            filled     = VALIDATION_AGENT.format(plan_json=json.dumps(plan, indent=2))
            llm_result = call_gemini_json(filled, use_pro=True)
        except Exception as e:
            print(f"      ⚠️  LLM validation failed ({e}), using rule-based only.")
            llm_result = {"errors": [], "confidence_score": 0.7,
                          "missing_info": [], "assumptions_made": [], "ai_notes": []}
    else:
        llm_result = {
            "errors": [],
            "confidence_score": plan.get("confidence_score", 1.0),
            "missing_info": plan.get("missing_info", []),
            "assumptions_made": plan.get("assumptions_made", []),
            "ai_notes": plan.get("ai_notes", []),
        }

    # Merge and de-duplicate
    all_errors = _dedup_errors(rule_issues + llm_result.get("errors", []))

    critical_count = sum(1 for e in all_errors if e.get("severity") == "critical")
    warning_count  = sum(1 for e in all_errors if e.get("severity") == "warning")
    passed         = critical_count == 0

    if config.VERBOSE:
        status = "✅ PASSED" if passed else "❌ FAILED"
        score  = llm_result.get("confidence_score", 0)
        print(f"      {status} | {critical_count} critical | {warning_count} warnings | confidence: {score:.0%}")
        for e in all_errors:
            icon = "🔴" if e["severity"] == "critical" else ("🟡" if e["severity"] == "warning" else "💡")
            print(f"         {icon}  [{e['category']}] {e['issue']}")

    return {
        "validation_passed":   passed,
        "confidence_score":    llm_result.get("confidence_score", 0.0),
        "errors":              all_errors,
        "missing_info":        llm_result.get("missing_info", []),
        "assumptions_made":    llm_result.get("assumptions_made", []),
        "ai_notes":            llm_result.get("ai_notes", []),
        "validation_warnings": [e["issue"] for e in all_errors if e["severity"] == "warning"],
    }
