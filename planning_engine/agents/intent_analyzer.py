# ============================================================
# agents/intent_analyzer.py
# ============================================================

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config
from core.gemini_client import call_gemini_json
from core.prompt_loader import load_prompt_template

INTENT_ANALYZER = load_prompt_template("intent_analyzer.md")


def analyze_intent(prompt: str, max_questions: int = 3) -> dict:
    """
    Stage 1 — Understand what the user wants to build.
    Returns a dict describing domain, complexity, modules, confidence, etc.
    """
    if config.VERBOSE:
        print("  🔍  Analyzing intent...")

    filled_prompt = INTENT_ANALYZER.format(prompt=prompt, max_questions=max_questions)
    result = call_gemini_json(filled_prompt, use_pro=False)

    if config.VERBOSE:
        confidence = result.get("confidence", 0)
        domain     = result.get("domain", "unknown")
        complexity = result.get("complexity", "unknown")
        print(f"      Domain: {domain} | Complexity: {complexity} | Confidence: {confidence:.0%}")

    return result


# def analyze_intent(prompt: str) -> dict:
#     """
#     Stage 1 — Understand what the user wants to build.
#     Returns a dict describing domain, complexity, modules, confidence, etc.
#     """
#     if config.VERBOSE:
#         print("  🔍  Analyzing intent...")

#     filled_prompt = INTENT_ANALYZER.format(prompt=prompt)
#     result = call_gemini_json(filled_prompt, use_pro=False)

#     if config.VERBOSE:
#         confidence = result.get("confidence", 0)
#         domain     = result.get("domain", "unknown")
#         complexity = result.get("complexity", "unknown")
#         print(f"      Domain: {domain} | Complexity: {complexity} | Confidence: {confidence:.0%}")

#     return result
