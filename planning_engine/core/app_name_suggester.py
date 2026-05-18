# ============================================================
# core/app_name_suggester.py - App name suggestions
# ============================================================

import json
import re

from core.gemini_client import call_gemini_json


def _fallback_app_name(prompt: str, intent: dict) -> str:
    app_type = (intent.get("app_type") or "").lower()
    domain = (intent.get("domain") or "").lower()
    prompt_lower = prompt.lower()

    if "attendance" in prompt_lower or "attendence" in prompt_lower or "attendance" in app_type:
        return "Atendsia"
    if "food" in prompt_lower or "restaurant" in prompt_lower or domain == "food_delivery":
        return "QuickBite"
    if "ride" in prompt_lower or "taxi" in prompt_lower or domain == "transport":
        return "RideFlow"
    if "shop" in prompt_lower or "store" in prompt_lower or domain == "ecommerce":
        return "ShopFlow"
    if "finance" in prompt_lower or "budget" in prompt_lower or domain == "finance":
        return "MoneyPilot"
    if "health" in prompt_lower or "fitness" in prompt_lower or domain == "health":
        return "WellTrack"
    if "learn" in prompt_lower or "education" in prompt_lower or domain == "education":
        return "LearnLoop"
    if "task" in prompt_lower or "todo" in prompt_lower or domain == "productivity":
        return "TaskPilot"

    words = [
        word.capitalize()
        for word in app_type.replace("-", " ").split()
        if word and word not in {"app", "application", "mobile", "flutter"}
    ]
    if words:
        return "".join(words[:2]) + "App"
    return "SmartApp"


def _clean_app_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9 ]", "", name).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        return ""
    return "".join(word[:1].upper() + word[1:] for word in cleaned.split())


def suggest_app_name(prompt: str, intent: dict) -> str:
    existing_name = _clean_app_name(str(intent.get("app_name", "")))
    if existing_name:
        return existing_name

    fallback = _fallback_app_name(prompt, intent)
    suggestion_prompt = f"""
You are naming a Flutter app from the user's idea.

User idea:
\"\"\"{prompt}\"\"\"

Intent JSON:
{json.dumps(intent, indent=2)}

Return ONLY valid JSON:
{{
  "name": "<one short, brandable app name>"
}}

Rules:
- Suggest exactly one name.
- The name must match the user's app idea and domain.
- Keep it 1-2 words, easy to pronounce, and suitable as an app name.
- Do not include generic words like Flutter, mobile, application, or app.
- Do not explain the name.
"""

    try:
        result = call_gemini_json(suggestion_prompt, use_pro=False)
    except Exception:
        return fallback

    if not isinstance(result, dict):
        return fallback

    cleaned = _clean_app_name(str(result.get("name", "")))
    return cleaned or fallback
