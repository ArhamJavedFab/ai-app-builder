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
from core.navigation_contract import HOME_ROUTE, ROOT_ROUTE
from core.plan_profile import is_local_first_plan
from core.prompt_loader import load_prompt_template
import config

VALIDATION_AGENT = load_prompt_template("validation_agent.md")


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

    local_first = is_local_first_plan(plan)

    if not local_first:
        if backend_type and backend_type != "firebase":
            issues.append(_issue(
                "critical", "backend",
                f"backend_type is '{backend_type}', but cloud-backed plans must use Firebase.",
                "Set backend.backend_type to 'firebase'.",
            ))
        if backend.get("auth_provider") not in ("", "firebase_auth"):
            issues.append(_issue(
                "critical", "backend",
                f"auth_provider is '{backend.get('auth_provider')}', but cloud plans must use Firebase Auth.",
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
    else:
        if backend.get("needs_backend") is True:
            issues.append(_issue(
                "warning", "backend",
                "Local-only app has needs_backend: true.",
                "Set backend.needs_backend to false.",
            ))
        if backend.get("auth_provider") not in ("", "none"):
            issues.append(_issue(
                "warning", "backend",
                f"Local-only app should not use auth_provider '{backend.get('auth_provider')}'.",
                "Set backend.auth_provider to 'none'.",
            ))

    # ── 0. Stable IDs ─────────────────────────────────────────
    if not plan.get("project_id"):
        issues.append(_issue(
            "warning", "schema",
            "plan.project_id is missing.",
            "Run normalize_plan_ids or regenerate the plan.",
        ))

    def _dup_ids(items: list, label: str) -> None:
        seen_ids: dict[str, int] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            eid = item.get("id", "")
            if not eid:
                issues.append(_issue(
                    "warning", "schema",
                    f"{label} entry is missing 'id'.",
                    "Run normalize_plan_ids on the plan.",
                ))
                continue
            seen_ids[eid] = seen_ids.get(eid, 0) + 1
        for eid, count in seen_ids.items():
            if count > 1:
                issues.append(_issue(
                    "critical", "schema",
                    f"Duplicate {label} id '{eid}' appears {count} times.",
                    f"Ensure all {label} ids are unique.",
                ))

    _dup_ids(screens, "screen")
    _dup_ids(plan.get("database_tables", []), "database_table")

    screen_ids = {s.get("id") for s in screens if isinstance(s, dict) and s.get("id")}
    for route in nav.get("routes", []):
        if not isinstance(route, dict):
            continue
        sid = route.get("screen_id", "")
        if sid and sid not in screen_ids:
            issues.append(_issue(
                "critical", "navigation",
                f"Route '{route.get('path','')}' references unknown screen_id '{sid}'.",
                "Set screen_id to a valid id from screens[].id.",
            ))
        elif route.get("screen") and not sid:
            issues.append(_issue(
                "warning", "navigation",
                f"Route '{route.get('path','')}' has screen name but no screen_id.",
                "Run normalize_plan_ids to link screen_id.",
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

    # ── 1b. Navigation contract (codegen) ─────────────────────
    for screen in screens:
        if not isinstance(screen, dict):
            continue
        route = (screen.get("route") or "").strip()
        if route == ROOT_ROUTE:
            issues.append(_issue(
                "critical", "navigation",
                f"Screen '{screen.get('name','')}' uses forbidden route '/'.",
                f"Set route to '{HOME_ROUTE}' for the home shell screen.",
            ))

    initial_route = (nav.get("initial_route") or "").strip()
    if not initial_route:
        issues.append(_issue(
            "warning", "navigation",
            "navigation.initial_route is missing.",
            "Set initial_route (e.g. /splash or /home).",
        ))
    elif initial_route not in screen_routes:
        issues.append(_issue(
            "critical", "navigation",
            f"initial_route '{initial_route}' is not defined on any screen.",
            "Add a screen with that route or update initial_route.",
        ))

    valid_nav_paths = set(screen_routes) | routes
    for redirect in nav.get("redirects") or []:
        if not isinstance(redirect, dict):
            continue
        for key in ("from", "to"):
            path = (redirect.get(key) or "").strip()
            if not path:
                issues.append(_issue(
                    "warning", "navigation",
                    f"Redirect entry is missing '{key}'.",
                    "Each redirect needs from, when, and to.",
                ))
            elif path == ROOT_ROUTE:
                issues.append(_issue(
                    "critical", "navigation",
                    f"Redirect '{key}' uses forbidden route '/'.",
                    f"Use '{HOME_ROUTE}' instead of '/'.",
                ))
            elif path not in valid_nav_paths:
                issues.append(_issue(
                    "critical", "navigation",
                    f"Redirect '{key}' path '{path}' is not a known screen route.",
                    "Use only routes from screens[].route.",
                ))
        if not (redirect.get("when") or "").strip():
            issues.append(_issue(
                "warning", "navigation",
                "Redirect is missing 'when' condition.",
                "Set when (e.g. first_launch, permissions_granted).",
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
    if (
        not local_first
        and auth_provider
        and auth_provider not in ("none", "")
        and backend.get("needs_auth") is not False
    ):
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

    # ── 7. Screen api_calls without matching endpoint (cloud REST only) ──
    if not local_first:
        for screen in screens if backend_type != "firebase" else []:
            for call in screen.get("api_calls", []):
                call_lower = call.lower()
                if call_lower.startswith(("local storage:", "firestore:", "firebase")):
                    continue
                parts = call.strip().split()
                path = parts[-1] if parts else call
                if path and path not in endpoints:
                    issues.append(_issue(
                        "warning", "backend",
                        f"Screen '{screen.get('name','')}' has api_call '{call}' "
                        f"but '{path}' is not in backend.api_endpoints.",
                        f"Replace '{call}' with a Firebase SDK action and keep backend.api_endpoints empty.",
                    ))

    if local_first:
        arch_db = arch.get("local_database", "")
        profile = (plan.get("storage_profile") or "").lower()
        if arch_db == "device_gallery" and profile != "media":
            issues.append(_issue(
                "critical", "architecture",
                f"local_database is '{arch_db}' but storage_profile is '{profile}' (not a gallery app).",
                "Set flutter_architecture.local_database to match storage_profile (isar/hive).",
            ))
        backend_rules = " ".join(str(r) for r in (backend.get("security_rules") or []))
        if profile != "media" and "gallery" in backend_rules.lower():
            issues.append(_issue(
                "critical", "backend",
                "Local plan has gallery/photo security rules but app is not a media gallery.",
                "Replace backend.security_rules with profile-appropriate on-device rules.",
            ))
        for screen in screens:
            for call in screen.get("api_calls", []):
                if "firestore" in call.lower() or "firebase auth" in call.lower():
                    issues.append(_issue(
                        "warning", "backend",
                        f"Local-only plan: screen '{screen.get('name','')}' should not use '{call}'.",
                        "Use 'Local Storage: ...' actions instead.",
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
