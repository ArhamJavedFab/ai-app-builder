# ============================================================
# agents/requirement_extractor.py
# ============================================================

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.gemini_client import call_gemini_json
from core.prompt_templates import (
    CLARIFICATION_GENERATOR,
    REQUIREMENT_COMPLETENESS_AUDITOR,
)
import config


def _display_question(idx: int, q: dict) -> None:
    print(f"\n  ?  Q{idx}: {q.get('question', '')}")
    if q.get("why"):
        print(f"      Why: {q['why']}")
    options = q.get("options", [])
    if options:
        for i, opt in enumerate(options, 1):
            print(f"         {i}. {opt}")
        print(f"         {len(options) + 1}. Other - type your own answer")


def _ask_user(question: dict, idx: int) -> str:
    _display_question(idx, question)
    options = question.get("options", [])
    while True:
        raw = input("\n  >  Your answer: ").strip()
        if not raw:
            continue
        if raw.isdigit():
            choice = int(raw)
            if 1 <= choice <= len(options):
                return options[choice - 1]
        return raw


def _fallback_questions(intent: dict) -> list[dict]:
    domain = (intent.get("domain") or "").lower()
    if domain != "ecommerce":
        return [
            {
                "id": "core_scope",
                "question": "What are the must-have screens/features for the first version?",
                "why": "This keeps the plan focused on what you actually want built first.",
                "options": [
                    "Use sensible defaults",
                    "Basic app with auth, home, profile, settings",
                    "I will type the exact screens/features",
                ],
            }
        ]

    return [
        {
            "id": "products",
            "question": (
                "What products will the ecommerce app sell, and do products need "
                "variants like size, color, or age range?"
            ),
            "why": "Product structure changes screens, filters, cart, and database tables.",
            "options": [
                "Crochet baby clothing with size/color variants",
                "Simple products without variants",
                "I will type the exact product structure",
            ],
        },
        {
            "id": "checkout",
            "question": "How should checkout work in the first version?",
            "why": "Payments and orders change backend, database, and validation requirements.",
            "options": [
                "Online payment plus cash on delivery",
                "Cash on delivery only",
                "No checkout yet, catalog/contact only",
            ],
        },
        {
            "id": "auth_profile",
            "question": (
                "Should customers create accounts with profile, addresses, order "
                "history, and settings?"
            ),
            "why": "Auth changes protected routes, user tables, and profile screens.",
            "options": [
                "Yes, full customer account",
                "Guest checkout with optional account",
                "No accounts in first version",
            ],
        },
        {
            "id": "store_admin",
            "question": "Do you need an admin/store-owner area to manage products and orders?",
            "why": "Admin features add roles, protected screens, backend endpoints, and database rules.",
            "options": [
                "Yes, include admin product/order management",
                "No, customer app only",
                "Later, post-MVP",
            ],
        },
        {
            "id": "visual_direction",
            "question": "What visual style should the app use?",
            "why": "Design direction changes colors, typography, components, and accessibility notes.",
            "options": [
                "High contrast, warm, engaging for moms",
                "Soft pastel baby boutique style",
                "Luxury handmade brand style",
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


def extract_requirements(prompt: str, intent: dict, force: bool = False) -> dict:
    """
    Stage 2 - ask clarifying questions until the plan has enough real context.
    Returns a dict of {question_id: {question, answer}}.
    """
    if config.VERBOSE:
        print("  Checking requirement clarity...")

    clarifications: dict = {}

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

