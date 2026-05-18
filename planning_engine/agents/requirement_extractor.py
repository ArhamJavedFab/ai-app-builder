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


def _question_with_examples(q: dict) -> str:
    question = q.get("question", "")
    examples = q.get("examples") or q.get("options") or []
    if examples:
        question = f"{question} (e.g. {', '.join(examples)})"
    return question


def _display_question(idx: int, q: dict) -> None:
    print(f"\n  ?  Q{idx}: {_question_with_examples(q)}")
    if q.get("why"):
        print(f"      Why: {q['why']}")


def _ask_user(question: dict, idx: int) -> str:
    _display_question(idx, question)
    while True:
        raw = input("\n  >  Your answer: ").strip()
        if not raw:
            continue
        return raw


REQUIRED_STARTUP_QUESTIONS = [
    {
        "id": "app_name",
        "question": "What should the app be called?",
        "why": "This helps the plan use the right brand name.",
        "examples": [
            "infer a name from my idea",
            "BabyKnits",
        ],
    },
    {
        "id": "target_users",
        "question": "Who will mainly use this app?",
        "why": "This helps choose the right pages, wording, and design style.",
        "examples": [
            "moms and parents",
            "general customers",
        ],
    },
    {
        "id": "mvp_scope",
        "question": "What should customers be able to do in the first version?",
        "why": "This keeps the plan focused on what you actually want first.",
        "examples": [
            "browse products, add to cart, order, and manage profile",
            "browse products and contact me to order",
        ],
    },
    {
        "id": "business_management",
        "question": "Do you want to manage products and orders inside the app?",
        "why": "This decides whether the plan should include a shop owner area.",
        "examples": [
            "yes, include a simple owner/admin area",
            "customer app only for now",
            "maybe later",
        ],
    },
]


def ask_required_startup_questions(prompt: str, intent: dict) -> dict:
    if not config.ASK_REQUIRED_STARTUP_QUESTIONS:
        return {}

    print("\n  Before planning, I need a few required basics.\n")
    answers = {}
    for i, question in enumerate(REQUIRED_STARTUP_QUESTIONS, 1):
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
                "question": "What are the must-have pages or actions for the first version?",
                "why": "This keeps the plan focused on what you actually want built first.",
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
                "What kind of products will you sell, and do they come in choices "
                "like size, color, or age range?"
            ),
            "why": "This helps plan product pages, filters, and order details.",
            "examples": [
                "crochet baby clothing with size/color variants",
                "simple products without variants",
            ],
        },
        {
            "id": "checkout",
            "question": "How should customers place an order?",
            "why": "This decides what the cart and checkout flow should include.",
            "examples": [
                "online payment plus cash on delivery",
                "cash on delivery only",
                "customers contact me to order",
            ],
        },
        {
            "id": "auth_profile",
            "question": (
                "Should customers have an account with profile, addresses, order "
                "history, and settings?"
            ),
            "why": "This helps decide what should be inside the profile area.",
            "examples": [
                "full customer account",
                "guest checkout with optional account",
                "no accounts in first version",
            ],
        },
        {
            "id": "store_admin",
            "question": "Do you need a shop owner area to add products and see orders?",
            "why": "This decides whether the plan includes owner-only pages.",
            "examples": [
                "include product and order management",
                "customer app only",
                "later, post-MVP",
            ],
        },
        {
            "id": "visual_direction",
            "question": "What visual style should the app use?",
            "why": "This helps choose colors, fonts, and the overall feeling of the app.",
            "examples": [
                "high contrast, warm, engaging for moms",
                "soft pastel baby boutique style",
                "luxury handmade brand style",
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
