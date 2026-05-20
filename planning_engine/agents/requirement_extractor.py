# ============================================================
# agents/requirement_extractor.py
# ============================================================

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.gemini_client import call_gemini_json
from core.app_name_suggester import suggest_app_name
from core.prompt_templates import (
    CLARIFICATION_GENERATOR,
    REQUIREMENT_COMPLETENESS_AUDITOR,
    STARTUP_QUESTION_GENERATOR,
    CONVERSATIONAL_VALIDATOR,
)
import config


# ─────────────────────────────────────────────────────────────
# DISPLAY HELPERS
# ─────────────────────────────────────────────────────────────

def _print_divider() -> None:
    print("\n  " + "─" * 54)


def _print_auto_answered(auto: dict) -> None:
    """
    Print what the AI already figured out from the prompt.
    This replaces the generic 'app name / target users' questions entirely.
    """
    _print_divider()
    print("  ✦  Here's what I already know from your idea:\n")
    if auto.get("app_name"):
        print(f"     App name  →  {auto['app_name']}")
    if auto.get("domain"):
        print(f"     Domain    →  {auto['domain'].replace('_', ' ').title()}")
    if auto.get("platform"):
        print(f"     Platform  →  {auto['platform']}")
    if auto.get("inferred_notes"):
        print(f"\n     {auto['inferred_notes']}")
    _print_divider()


def _display_smart_question(idx: int, total: int, q: dict) -> None:
    """Render a smart question with numbered options.
    The tip line "(Press Enter to let AI decide)" is removed for a cleaner UI.
    """
    print(f"\n  Q{idx}/{total}  {q['question']}\n")
    options = q.get('options', [])
    for i, opt in enumerate(options, 1):
        marker = '◆' if i == 4 else '○'
        print(f"     {marker} {i}.  {opt}")


def validate_user_response(question: str, options: list, user_input: str) -> dict:
    """
    Call Gemini to validate the user response to a question.
    """
    if options:
        options_text = "\n".join(f"- {opt}" for opt in options)
    else:
        options_text = "No fixed options."

    filled = CONVERSATIONAL_VALIDATOR.format(
        question=question,
        options_text=options_text,
        user_input=user_input,
    )
    try:
        res = call_gemini_json(filled, use_pro=False)
        if isinstance(res, dict):
            return res
    except Exception as e:
        print(f"      ⚠️  Validation agent error: {e}")
    
    return {"is_valid": True, "chatbot_response": None}


def _ask_smart_question(q: dict, idx: int, total: int) -> str:
    """
    Show a numbered-option question. Returns the chosen option text,
    or the last option ('Let AI decide') on blank input.
    Validates that the input is 1–4 or blank.
    """
    _display_smart_question(idx, total, q)
    options = q.get("options", [])
    ai_option = options[-1] if options else "Let AI decide based on my idea"

    while True:
        try:
            raw = input("  >  Pick 1–4 or press Enter: ").strip()
        except (EOFError, KeyboardInterrupt):
            return ai_option

        # Blank = let AI decide
        if not raw:
            print(f"     ✓  AI will decide")
            return ai_option

        # Numeric pick
        if raw.isdigit():
            choice = int(raw)
            if 1 <= choice <= len(options):
                chosen = options[choice - 1]
                print(f"     ✓  {chosen}")
                return chosen
            else:
                print(f"     Please enter a number between 1 and {len(options)}, or press Enter.")
                continue

        # Free text — validate it
        validation = validate_user_response(
            q.get("question", ""),
            options,
            raw
        )
        if validation.get("is_valid", True):
            print(f"     ✓  Got it")
            return raw
        else:
            chatbot_response = validation.get("chatbot_response") or "It seems the answer is not valid; please answer the correct one."
            print(f"\n  🤖  {chatbot_response}")
            continue


# ─────────────────────────────────────────────────────────────
# SMART STARTUP QUESTIONS  (replaces generic name/users/scope)
# ─────────────────────────────────────────────────────────────

def _fallback_smart_questions(intent: dict) -> dict:
    """
    If Gemini fails, return domain-specific fallback questions.
    Never asks 'what is the app name?' or 'who will use this?'
    """
    domain = (intent.get("domain") or "").lower()

    if domain == "ecommerce":
        return {
            "auto_answered": {
                "app_name": intent.get("app_name") or "Your Store",
                "domain":   "ecommerce",
                "platform": "Flutter mobile app",
                "inferred_notes": "An e-commerce store app for buying and selling products.",
            },
            "questions": [
                {
                    "id": "product_type",
                    "question": "What are you selling?",
                    "options": [
                        "Physical products (clothes, accessories, handmade items)",
                        "Digital products (files, templates, courses)",
                        "Both physical and digital products",
                        "Let AI decide based on my idea",
                    ],
                },
                {
                    "id": "payment_method",
                    "question": "How do customers pay?",
                    "options": [
                        "Cash on delivery only",
                        "Online payment (card, wallet)",
                        "Both cash on delivery and online payment",
                        "Let AI decide based on my idea",
                    ],
                },
                {
                    "id": "admin_panel",
                    "question": "Do you need an owner/admin panel?",
                    "options": [
                        "Yes — manage products, orders, and customers inside the app",
                        "No — just the customer-facing store for now",
                        "Basic order notifications only",
                        "Let AI decide based on my idea",
                    ],
                },
            ],
        }

    if domain == "food_delivery":
        return {
            "auto_answered": {
                "app_name": intent.get("app_name") or "FoodApp",
                "domain": "food delivery",
                "platform": "Flutter mobile app",
                "inferred_notes": "A food ordering and delivery app.",
            },
            "questions": [
                {
                    "id": "restaurant_model",
                    "question": "One restaurant or multiple?",
                    "options": [
                        "Single restaurant (my own place)",
                        "Multiple restaurants on one platform",
                        "Cloud kitchen / delivery-only",
                        "Let AI decide based on my idea",
                    ],
                },
                {
                    "id": "driver_app",
                    "question": "Do drivers need a separate app?",
                    "options": [
                        "Yes — drivers get their own app",
                        "No — owner handles delivery manually",
                        "Third-party delivery (no driver app needed)",
                        "Let AI decide based on my idea",
                    ],
                },
            ],
        }

    if domain in ("health", "fitness"):
        return {
            "auto_answered": {
                "app_name": intent.get("app_name") or "FitApp",
                "domain": "health & fitness",
                "platform": "Flutter mobile app",
                "inferred_notes": "A health or fitness tracking app.",
            },
            "questions": [
                {
                    "id": "user_model",
                    "question": "Solo tracking or trainer–client?",
                    "options": [
                        "Solo — one person tracking their own progress",
                        "Trainer managing multiple clients",
                        "Community / group challenges",
                        "Let AI decide based on my idea",
                    ],
                },
                {
                    "id": "content_type",
                    "question": "What does the user track or consume?",
                    "options": [
                        "Workouts and exercises",
                        "Diet and nutrition",
                        "Both workouts and nutrition",
                        "Let AI decide based on my idea",
                    ],
                },
            ],
        }

    # Generic fallback for any other domain
    detected = ", ".join(intent.get("detected_modules") or ["core features"])
    return {
        "auto_answered": {
            "app_name": intent.get("app_name") or "Your App",
            "domain": domain or "general",
            "platform": "Flutter mobile app",
            "inferred_notes": f"Detected modules: {detected}.",
        },
        "questions": [
            {
                "id": "core_scope",
                "question": "What's the most important first feature?",
                "options": [
                    f"Start with {detected.split(',')[0].strip()} and keep it minimal",
                    "Build the full feature set from day one",
                    "MVP only — add features over time",
                    "Let AI decide based on my idea",
                ],
            },
            {
                "id": "user_accounts",
                "question": "Do users need accounts?",
                "options": [
                    "Yes — login, profile, and saved data",
                    "No — open access, no accounts",
                    "Optional guest mode + accounts",
                    "Let AI decide based on my idea",
                ],
            },
        ],
    }


def _generate_smart_questions(prompt: str, intent: dict) -> dict:
    """
    Call Gemini to generate smart, domain-specific questions with 4 options each.
    Falls back to domain-specific hardcoded questions if Gemini fails.
    Returns {"auto_answered": {...}, "questions": [...]}
    """
    suggested_name = suggest_app_name(prompt, intent)
    filled = STARTUP_QUESTION_GENERATOR.format(
        prompt=prompt,
        intent_json=json.dumps(intent, indent=2),
        suggested_name=suggested_name,
    )
    try:
        result = call_gemini_json(filled, use_pro=False)
    except Exception:
        return _fallback_smart_questions(intent)

    if not isinstance(result, dict):
        return _fallback_smart_questions(intent)

    questions = result.get("questions", [])
    auto      = result.get("auto_answered", {})

    # Validate: each question must have exactly 4 options
    valid_questions = []
    for q in questions:
        opts = q.get("options", [])
        if not opts:
            continue
        # Ensure option 4 is always the AI-decide option
        while len(opts) < 4:
            opts.append("Let AI decide based on my idea")
        opts = opts[:4]
        opts[3] = "Let AI decide based on my idea"
        q["options"] = opts
        valid_questions.append(q)

    if not valid_questions:
        return _fallback_smart_questions(intent)

    # Ensure auto_answered has app_name at minimum
    if not auto.get("app_name"):
        auto["app_name"] = suggested_name

    return {"auto_answered": auto, "questions": valid_questions}


def ask_required_startup_questions(prompt: str, intent: dict) -> dict:
    """
    Public entry point for Stage 2 startup questions.

    Flow:
      1. Call Gemini to generate 2–4 smart domain-specific questions
      2. Print what the AI already inferred (auto_answered)
      3. Ask ONLY the remaining intelligent questions with 4 options
      4. Blank input → option 4 'Let AI decide'
      5. Return clarifications dict for downstream agents

    This replaces the old generic: app_name / target_users / mvp_scope / management_scope
    """
    if not config.ASK_REQUIRED_STARTUP_QUESTIONS:
        return {}

    data      = _generate_smart_questions(prompt, intent)
    auto      = data.get("auto_answered", {})
    questions = data.get("questions", [])

    # Show what was auto-inferred — no need to ask these
    _print_auto_answered(auto)

    if not questions:
        print("  ✅  All details inferred from your prompt. Proceeding to planning.\n")
        return {"_auto": {"question": "auto-inferred", "answer": json.dumps(auto)}}

    print(f"\n  Just {len(questions)} quick question(s) and we're ready to build your plan.\n")

    answers: dict = {}
    total = len(questions)

    for i, q in enumerate(questions, 1):
        qid    = q.get("id") or f"q{i}"
        answer = _ask_smart_question(q, i, total)
        answers[qid] = {
            "question": q.get("question", ""),
            "answer":   answer,
        }

    # Store auto-answered fields too so downstream agents use them
    answers["_auto"] = {
        "question": "auto-inferred",
        "answer":   json.dumps(auto),
    }

    print(f"\n  ✅  Got it — generating your plan now.\n")
    return answers


# ─────────────────────────────────────────────────────────────
# WEB API HELPERS  (FastAPI / view layer — unchanged interface)
# ─────────────────────────────────────────────────────────────

def build_required_startup_questions(prompt: str, intent: dict) -> list[dict]:
    if not config.ASK_REQUIRED_STARTUP_QUESTIONS:
        return []
    data = _generate_smart_questions(prompt, intent)
    return data.get("questions", [])


def build_startup_answers(questions: list[dict], raw_answers: dict[str, str]) -> dict:
    answers = {}
    for q in questions:
        qid    = q.get("id", "")
        answer = str(raw_answers.get(qid, "")).strip()
        opts   = q.get("options", [])
        # Resolve numeric pick from web UI
        if answer.isdigit() and 1 <= int(answer) <= len(opts):
            answer = opts[int(answer) - 1]
        if not answer:
            answer = opts[-1] if opts else "Let AI decide based on my idea"
        answers[qid] = {"question": q.get("question", ""), "answer": answer}
    return answers


# ─────────────────────────────────────────────────────────────
# REQUIREMENT COMPLETENESS  (rounds 2+ — unchanged logic)
# ─────────────────────────────────────────────────────────────

def _fallback_questions(intent: dict) -> list[dict]:
    domain = (intent.get("domain") or "").lower()
    if domain != "ecommerce":
        return [{"id": "core_scope", "question": "Must-have first-version feature?",
                 "examples": ["use sensible defaults", "home, profile, and settings"]}]
    return [
        {"id": "products",         "question": "Product type?",      "examples": ["clothing with variants", "simple products"]},
        {"id": "checkout",         "question": "Checkout method?",   "examples": ["cash on delivery", "online payment"]},
        {"id": "auth_profile",     "question": "Customer accounts?", "examples": ["full account", "guest checkout"]},
        {"id": "store_admin",      "question": "Owner panel?",       "examples": ["yes, manage products", "customer app only"]},
        {"id": "visual_direction", "question": "Visual style?",      "examples": ["modern minimal", "soft pastel"]},
    ]


def _audit_completeness(prompt: str, intent: dict, clarifications: dict) -> dict:
    filled = REQUIREMENT_COMPLETENESS_AUDITOR.format(
        prompt=prompt,
        intent_json=json.dumps(intent, indent=2),
        clarifications_json=json.dumps(clarifications, indent=2),
        max_questions=config.MAX_CLARIFICATION_QUESTIONS,
    )
    return call_gemini_json(filled, use_pro=False)


def _legacy_question_generation(prompt: str, intent: dict) -> list[dict]:
    filled = CLARIFICATION_GENERATOR.format(
        intent_json=json.dumps(intent, indent=2),
        prompt=prompt,
        max_questions=config.MAX_CLARIFICATION_QUESTIONS,
    )
    result = call_gemini_json(filled, use_pro=False)
    if not result.get("needs_clarification", False):
        return []
    return result.get("questions", [])


def _display_followup_question(idx: int, q: dict) -> None:
    """For round 2+ questions — simpler display, no numbered options."""
    question = q.get("question", "")
    examples = q.get("examples") or []
    if examples:
        question = f"{question} (e.g. {', '.join(str(e)[:50] for e in examples[:2])})"
    print(f"\n  ?  Q{idx}: {question}")


def _ask_followup(question: dict, idx: int) -> str:
    _display_followup_question(idx, question)
    while True:
        try:
            raw = input("\n  >  Your answer: ").strip()
        except (EOFError, KeyboardInterrupt):
            return "use sensible defaults"
        if not raw:
            continue

        validation = validate_user_response(
            question.get("question", ""),
            question.get("examples", []),
            raw
        )
        if validation.get("is_valid", True):
            return raw
        else:
            chatbot_response = validation.get("chatbot_response") or "It seems the answer is not valid; please answer the correct one."
            print(f"\n  🤖  {chatbot_response}")
            continue


def extract_requirements(
    prompt: str,
    intent: dict,
    force: bool = False,
    initial_clarifications: dict | None = None,
) -> dict:
    """
    Stage 2 continued — completeness audit + follow-up questions.
    Called AFTER ask_required_startup_questions().
    Uses plain open-ended questions (not numbered options) for follow-ups.
    """
    if config.VERBOSE:
        print("  Checking requirement clarity...")

    clarifications: dict = dict(initial_clarifications or {})

    for round_no in range(1, config.MAX_CLARIFICATION_ROUNDS + 1):
        audit       = _audit_completeness(prompt, intent, clarifications)
        score       = float(audit.get("completeness_score", 0.0) or 0.0)
        clear_enough = bool(audit.get("is_clear_enough", False)) and score >= config.MIN_REQUIREMENT_COMPLETENESS

        if clear_enough and not force:
            if config.VERBOSE:
                print(f"      Requirements clear enough ({score:.0%}).")
            return clarifications

        questions  = audit.get("questions", []) or _legacy_question_generation(prompt, intent) or _fallback_questions(intent)
        unanswered = [q for q in questions[:config.MAX_CLARIFICATION_QUESTIONS]
                      if q.get("id", "") not in clarifications]

        if not unanswered:
            return clarifications

        print(f"\n  I need {len(unanswered)} more answer(s) (clarity: {score:.0%}, round {round_no}).\n")

        for i, q in enumerate(unanswered, 1):
            qid    = q.get("id") or f"round_{round_no}_q{i}"
            answer = _ask_followup(q, i)
            clarifications[qid] = {"question": q.get("question", ""), "answer": answer}

        force = False

    print()
    return clarifications
