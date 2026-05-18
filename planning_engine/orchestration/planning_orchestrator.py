# ============================================================
# orchestration/planning_orchestrator.py
# ============================================================

import sys, os, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.schema import MasterPlan, empty_plan
from core.gemini_client import call_gemini_json
from core.app_name_suggester import suggest_app_name
from core.plan_editor import apply_patch
from core.prompt_templates import PLAN_REPAIRER
from agents.intent_analyzer       import analyze_intent
from agents.requirement_extractor import (
    ask_required_startup_questions,
    extract_requirements,
)
from agents.feature_planner       import plan_features
from agents.screen_planner        import plan_screens
from agents.navigation_planner    import plan_navigation
from agents.backend_planner       import plan_backend
from agents.database_planner      import plan_database
from agents.architecture_planner  import plan_architecture, plan_design_system
from validation.validator         import validate_plan
import config


def _separator(label: str) -> None:
    width = 60
    print(f"\n{'─' * width}")
    print(f"  STAGE: {label}")
    print(f"{'─' * width}")


def _run_required_stage(label: str, fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        raise RuntimeError(
            f"Stage failed: {label}\n{e}\n\n"
            "No later stages were run because this stage did not produce a trusted result."
        ) from e


def _prompt_needs_clarification(prompt: str, intent: dict) -> bool:
    words = [w for w in prompt.split() if w.strip()]
    if len(words) < 25:
        return True
    prompt_lower = prompt.lower()
    important_terms = {
        "target":   ["target", "audience", "users", "moms", "customer"],
        "screens":  ["screen", "page", "home", "profile", "shop", "cart"],
        "checkout": ["checkout", "payment", "cash", "order", "delivery"],
        "auth":     ["login", "signup", "account", "profile", "guest"],
        "design":   ["color", "style", "theme", "contrast", "brand"],
    }
    missing_count = sum(
        1
        for terms in important_terms.values()
        if not any(term in prompt_lower for term in terms)
    )
    if (intent.get("domain") or "").lower() == "ecommerce" and missing_count >= 2:
        return True
    return False


def _apply_plan_dict(plan: MasterPlan, data: dict) -> None:
    for key in plan.to_dict().keys():
        if key in data:
            setattr(plan, key, data[key])


def _wants_suggested_name(answer: str) -> bool:
    normalized = answer.strip().lower()
    suggestion_terms = {
        "infer",
        "suggest",
        "suggest one",
        "suggest a name",
        "you suggest",
        "generate",
        "auto",
        "automatic",
        "use sensible default",
        "use sensible defaults",
    }
    return any(term in normalized for term in suggestion_terms)


def _store_validation(plan: MasterPlan, validation: dict) -> None:
    plan.validation_passed   = validation["validation_passed"]
    plan.confidence_score    = validation["confidence_score"]
    plan.missing_info        = validation["missing_info"]
    plan.assumptions_made    = validation["assumptions_made"]
    plan.ai_notes            = validation["ai_notes"]
    plan.validation_warnings = validation["validation_warnings"]


def _apply_plan_patches(plan: MasterPlan, repair_result: dict) -> None:
    patches = repair_result.get("patches", [])
    if not isinstance(patches, list):
        raise RuntimeError("Plan repair did not return a patches list.")
    updated = plan.to_dict()
    for patch in patches:
        try:
            updated = apply_patch(updated, patch)
        except Exception as e:
            print(f"      ⚠️  Skipping bad patch {patch}: {e}")
    _apply_plan_dict(plan, updated)


def _validate_and_repair(plan: MasterPlan) -> None:
    """
    Validate the plan. If it fails, attempt repairs up to
    MAX_VALIDATION_REPAIR_ATTEMPTS times.
    """
    validation = _run_required_stage("Plan Validation", validate_plan, plan.to_dict())
    _store_validation(plan, validation)

    for attempt in range(1, config.MAX_VALIDATION_REPAIR_ATTEMPTS + 1):
        if plan.validation_passed:
            return

        # Only repair critical + warning issues, not suggestions
        repairable_errors = [
            e for e in validation.get("errors", [])
            if e.get("severity") in ("critical", "warning")
        ]
        if not repairable_errors:
            # Only suggestions left — mark as passed
            plan.validation_passed = True
            return

        print(f"\n  🔧  Repairing plan — attempt {attempt}/{config.MAX_VALIDATION_REPAIR_ATTEMPTS}...")
        print(f"      Fixing {len(repairable_errors)} issue(s)...")

        repair_validation = {"errors": repairable_errors, **{
            k: v for k, v in validation.items() if k != "errors"
        }}

        try:
            repair_result = _run_required_stage(
                "Plan Repair",
                call_gemini_json,
                PLAN_REPAIRER.format(
                    validation_json=json.dumps(repair_validation, indent=2),
                    plan_json=json.dumps(plan.to_dict(), indent=2),
                ),
                True,  # use_pro
            )
        except Exception as e:
            print(f"      ⚠️  Repair generation failed: {e}")
            break

        if not isinstance(repair_result, dict):
            print("      ⚠️  Repair agent returned unexpected format.")
            break

        _apply_plan_patches(plan, repair_result)

        if config.VERBOSE:
            summary = repair_result.get("summary", "Applied validation repair patches.")
            print(f"      ✓  {summary}")

        # Re-validate after repair
        validation = _run_required_stage(
            f"Plan Validation (after repair {attempt})",
            validate_plan,
            plan.to_dict(),
        )
        _store_validation(plan, validation)

    if not plan.validation_passed:
        # Check if only suggestions remain — these don't block the plan
        remaining_critical = [
            e for e in validation.get("errors", [])
            if e.get("severity") == "critical"
        ]
        if not remaining_critical:
            plan.validation_passed = True
            if config.VERBOSE:
                warnings_left = sum(
                    1 for e in validation.get("errors", [])
                    if e.get("severity") == "warning"
                )
                print(f"\n  ✅  No critical errors remain ({warnings_left} warnings noted).")
            return

        critical = [e.get("issue", "") for e in remaining_critical[:5]]
        issue_text = "\n".join(f"  - {i}" for i in critical)
        raise RuntimeError(
            f"Plan still has {len(remaining_critical)} critical error(s) after repair:\n"
            f"{issue_text}\n\n"
            "Try adding more detail to your prompt or increasing MAX_VALIDATION_REPAIR_ATTEMPTS."
        )


def run_planning_pipeline(user_prompt: str) -> MasterPlan:
    """
    Runs the full multi-agent planning pipeline.
    Returns a populated MasterPlan instance.
    """
    start = time.time()
    plan  = empty_plan()

    # ── Stage 1: Intent ──────────────────────────────────────
    _separator("Intent Analysis")
    intent = _run_required_stage("Intent Analysis", analyze_intent, user_prompt)

    plan.app_name     = intent.get("app_name", "")
    plan.app_type     = intent.get("app_type", "")
    plan.platform     = intent.get("platform", "flutter_cross_platform")
    plan.summary      = intent.get("core_goal", "")
    plan.tagline      = intent.get("tagline", "")
    plan.target_users = intent.get("target_users", [])
    plan.user_roles   = intent.get("user_roles", [])

    # ── Stage 2: Clarification ───────────────────────────────
    _separator("Requirement Clarification")
    clarifications = _run_required_stage(
        "Required Startup Questions",
        ask_required_startup_questions,
        user_prompt,
        intent,
    )
    confidence = intent.get("confidence", 1.0)
    force_clarification = (
        confidence < config.MIN_INTENT_CONFIDENCE
        or _prompt_needs_clarification(user_prompt, intent)
    )
    if force_clarification:
        clarifications = _run_required_stage(
            "Requirement Clarification",
            extract_requirements,
            user_prompt,
            intent,
            True,
            clarifications,
        )
    else:
        if config.VERBOSE:
            print(f"  ✅  Confidence {confidence:.0%} — skipping extra clarification.")

    # Apply app name from clarifications if provided
    app_name_answer = clarifications.get("app_name", {}).get("answer", "")
    if app_name_answer and _wants_suggested_name(app_name_answer):
        plan.app_name = suggest_app_name(user_prompt, intent)
        if config.VERBOSE:
            print(f"  Suggested app name: {plan.app_name}")
    elif app_name_answer:
        plan.app_name = app_name_answer
    elif not plan.app_name:
        plan.app_name = suggest_app_name(user_prompt, intent)

    # ── Stage 3: Features ────────────────────────────────────
    _separator("Feature Planning")
    features_data = _run_required_stage("Feature Planning", plan_features, intent, clarifications)
    plan.features          = features_data.get("features", [])
    plan.mvp_features      = features_data.get("mvp_features", [])
    plan.post_mvp_features = features_data.get("post_mvp_features", [])

    # ── Stage 4: Screens ─────────────────────────────────────
    _separator("Screen Planning")
    screens_data = _run_required_stage("Screen Planning", plan_screens, intent, features_data)
    plan.screens = screens_data.get("screens", [])

    # ── Stage 5: Navigation ──────────────────────────────────
    _separator("Navigation Planning")
    plan.navigation = _run_required_stage("Navigation Planning", plan_navigation, intent, screens_data)

    # ── Stage 6: Backend ─────────────────────────────────────
    _separator("Backend Planning")
    backend_data = _run_required_stage("Backend Planning", plan_backend, intent, features_data, screens_data)
    plan.backend = backend_data

    # ── Stage 7: Database ────────────────────────────────────
    _separator("Database Planning")
    db_data = _run_required_stage("Database Planning", plan_database, intent, features_data, backend_data)
    plan.database_tables = db_data.get("tables", [])

    # ── Stage 8a: Architecture ───────────────────────────────
    _separator("Flutter Architecture Planning")
    # Pass backend so cart_strategy is set consistently
    arch_data = _run_required_stage("Flutter Architecture Planning", plan_architecture, intent, features_data, backend_data)
    plan.flutter_architecture = {
        "state_management":        arch_data.get("state_management", "riverpod"),
        "state_management_reason": arch_data.get("state_management_reason", ""),
        "architecture_pattern":    arch_data.get("architecture_pattern", "feature_first_clean_architecture"),
        "cart_strategy":           arch_data.get("cart_strategy", "server"),
        "folder_structure":        arch_data.get("folder_structure", []),
        "navigation_package":      arch_data.get("navigation_package", "go_router"),
        "network_layer":           arch_data.get("network_layer", "dio"),
        "local_database":          arch_data.get("local_database", "isar"),
        "offline_first":           arch_data.get("offline_first", False),
        "modular":                 arch_data.get("modular", True),
        "flavors":                 arch_data.get("flavors", []),
    }
    plan.flutter_dependencies = arch_data.get("flutter_dependencies", [])
    plan.dev_dependencies     = arch_data.get("dev_dependencies", [])
    plan.testing_strategy     = arch_data.get("testing_strategy", {})
    plan.security_rules       = arch_data.get("security_rules", [])
    plan.performance_notes    = arch_data.get("performance_notes", [])
    plan.accessibility_notes  = arch_data.get("accessibility_notes", [])

    # ── Stage 8b: Design System ──────────────────────────────
    _separator("Design System Planning")
    # Pass clarifications so user-specified colors are always honoured
    plan.design_system = _run_required_stage(
        "Design System Planning",
        plan_design_system,
        intent,
        clarifications,    # ← NEW: branding notes extracted from user answers
    )

    # ── Stage 9: Validation + Repair ────────────────────────
    _separator("Plan Validation")
    _validate_and_repair(plan)

    elapsed = time.time() - start
    print(f"\n{'═' * 60}")
    print(f"  🎉  Planning complete in {elapsed:.1f}s")
    print(f"{'═' * 60}\n")

    return plan
