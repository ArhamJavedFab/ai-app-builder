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
)
import config


def _question_with_examples(q: dict) -> str:
    question = q.get("question", "")
    examples = q.get("examples") or q.get("options") or []
    if examples:
        short_examples = [str(example)[:50] for example in examples[:2]]
        question = f"{question} (e.g. {', '.join(short_examples)})"
    return question


def _display_question(idx: int, q: dict) -> None:
    print(f"\n  ?  Q{idx}: {_question_with_examples(q)}")
    if q.get("default_answer"):
        print(f"      Press Enter to use {q['default_answer']}, or type your own.")


def _ask_user(question: dict, idx: int) -> str:
    _display_question(idx, question)
    while True:
        raw = input("\n  >  Your answer: ").strip()
        if not raw and question.get("default_answer"):
            return question["default_answer"]
        if not raw:
            continue
        return raw


QUESTION_TEXT_BY_ID = {
    "app_name": "What is the app name?",
    "target_users": "Who will use this app?",
    "mvp_scope": "What features come first?",
    "management_scope": "Is this personal or shared?",
}


def _normalize_question_text(question: dict) -> dict:
    question_id = str(question.get("id", ""))
    if question_id in QUESTION_TEXT_BY_ID:
        question["question"] = QUESTION_TEXT_BY_ID[question_id]
    return question


def _required_startup_questions(prompt: str, intent: dict) -> list[dict]:
    suggested_name = suggest_app_name(prompt, intent)
    filled = STARTUP_QUESTION_GENERATOR.format(
        prompt=prompt,
        intent_json=json.dumps(intent, indent=2),
        suggested_name=suggested_name,
    )

    try:
        result = call_gemini_json(filled, use_pro=False)
    except Exception:
        return _fallback_required_startup_questions(prompt, intent, suggested_name)

    questions = result.get("questions", []) if isinstance(result, dict) else []
    if not isinstance(questions, list) or not questions:
        return _fallback_required_startup_questions(prompt, intent, suggested_name)

    expected_ids = ["app_name", "target_users", "mvp_scope", "management_scope"]
    by_id = {
        str(question.get("id", "")): question
        for question in questions
        if isinstance(question, dict)
    }

    ordered_questions: list[dict] = []
    fallback_questions = {
        q["id"]: q
        for q in _fallback_required_startup_questions(prompt, intent, suggested_name)
    }
    for question_id in expected_ids:
        question = by_id.get(question_id) or fallback_questions[question_id]
        if question_id == "app_name":
            question["default_answer"] = question.get("default_answer") or suggested_name
            question["examples"] = question.get("examples") or [suggested_name]
        ordered_questions.append(_normalize_question_text(question))
    return ordered_questions


def _fallback_required_startup_questions(
    prompt: str,
    intent: dict,
    suggested_name: str,
) -> list[dict]:
    app_type = intent.get("app_type") or "this app"
    users = intent.get("target_users") or ["people who need this app"]
    modules = intent.get("detected_modules") or ["core tracking", "profile", "settings"]

    user_examples = [str(user) for user in users[:3]]
    if len(user_examples) < 3:
        user_examples.append(f"people using {app_type}")
    if len(user_examples) < 3:
        user_examples.append("use sensible defaults")

    module_text = ", ".join(str(module).lower() for module in modules[:3])
    return [
        {
            "id": "app_name",
            "question": "What is the app name?",
            "examples": [suggested_name],
            "default_answer": suggested_name,
        },
        {
            "id": "target_users",
            "question": "Who will use this app?",
            "examples": user_examples[:3],
        },
        {
            "id": "mvp_scope",
            "question": "What features come first?",
            "examples": [
                module_text,
                "use the core features from my prompt",
                "use sensible defaults",
            ],
        },
        {
            "id": "management_scope",
            "question": "Is this personal or shared?",
            "examples": [
                "personal-only for now",
                "include coach or reviewer access",
                "use sensible defaults",
            ],
        },
    ]


def ask_required_startup_questions(prompt: str, intent: dict) -> dict:
    if not config.ASK_REQUIRED_STARTUP_QUESTIONS:
        return {}

    print("\n  Before planning, I need a few required basics.\n")
    answers = {}
    for i, question in enumerate(_required_startup_questions(prompt, intent), 1):
        answer = _ask_user(question, i)
        answers[question["id"]] = {
            "question": question["question"],
            "answer": answer,
        }
    return answers


def _fallback_questions(intent: dict) -> list[dict]:
    domain = (intent.get("domain") or "").lower()
    if domain != "ecommerce":
        return [
            {
                "id": "core_scope",
                "question": "Must-have first-version actions?",
                "examples": [
                    "use sensible defaults",
                    "home, account/profile, and settings",
                ],
            }
        ]

    return [
        {
            "id": "products",
            "question": (
                "Product type?"
            ),
            "examples": [
                "clothing with size/color variants",
                "simple products without variants",
            ],
        },
        {
            "id": "checkout",
            "question": "Checkout method?",
            "examples": [
                "online payment plus cash on delivery",
                "cash on delivery only",
                "customers contact me to order",
            ],
        },
        {
            "id": "auth_profile",
            "question": (
                "Customer accounts?"
            ),
            "examples": [
                "full customer account",
                "guest checkout with optional account",
                "no accounts in first version",
            ],
        },
        {
            "id": "store_admin",
            "question": "Owner area?",
            "examples": [
                "include product and order management",
                "customer app only",
                "later, post-MVP",
            ],
        },
        {
            "id": "visual_direction",
            "question": "Visual style?",
            "examples": [
                "modern and high contrast",
                "soft and minimal",
                "premium brand style",
            ],
        },
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


def extract_requirements(
    prompt: str,
    intent: dict,
    force: bool = False,
    initial_clarifications: dict | None = None,
) -> dict:
    """
    Stage 2 - ask clarifying questions until the plan has enough real context.
    Returns a dict of {question_id: {question, answer}}.
    """
    if config.VERBOSE:
        print("  Checking requirement clarity...")

    clarifications: dict = dict(initial_clarifications or {})

    for round_no in range(1, config.MAX_CLARIFICATION_ROUNDS + 1):
        audit = _audit_completeness(prompt, intent, clarifications)
        score = float(audit.get("completeness_score", 0.0) or 0.0)
        clear_enough = (
            bool(audit.get("is_clear_enough", False))
            and score >= config.MIN_REQUIREMENT_COMPLETENESS
        )

        if clear_enough and not force:
            if config.VERBOSE:
                print(f"      Requirements clear enough ({score:.0%}).")
            return clarifications

        questions = audit.get("questions", [])
        if not questions:
            questions = _legacy_question_generation(prompt, intent)
        if not questions:
            questions = _fallback_questions(intent)

        unanswered = [
            q
            for q in questions[: config.MAX_CLARIFICATION_QUESTIONS]
            if q.get("id", "") not in clarifications
        ]
        if not unanswered:
            return clarifications

        print(
            f"\n  I need {len(unanswered)} answer(s) before generating the plan "
            f"(clarity: {score:.0%}, round {round_no}).\n"
        )

        for i, q in enumerate(unanswered, 1):
            qid = q.get("id") or f"round_{round_no}_q{i}"
            answer = _ask_user(q, i)
            clarifications[qid] = {
                "question": q.get("question", ""),
                "answer": answer,
            }

        force = False

    print()
    return clarifications
