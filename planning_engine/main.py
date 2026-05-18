#!/usr/bin/env python3
# ============================================================
# main.py — Planning Engine CLI entry point
#
# Usage:
#   python main.py
#   python main.py --prompt "Build a food delivery app..."
#   python main.py --prompt "..." --output my_plan.json
# ============================================================

import argparse
import os
import sys

# Make sure local imports work from any working directory
sys.path.insert(0, os.path.dirname(__file__))

from orchestration.planning_orchestrator import run_planning_pipeline
from core.plan_editor import run_chat_editor
from core.summary import print_concise_summary, save_summary
import config


BANNER = """
╔══════════════════════════════════════════════════════════╗
║         🚀  Flutter App Planning Engine  🚀              ║
║         Powered by Gemini AI                             ║
╚══════════════════════════════════════════════════════════╝
"""


def get_prompt_from_user() -> str:
    print("\n  📝  Describe the Flutter app you want to build.")
    print("  Tip: Include target users, key features, and any special requirements.\n")
    lines = []
    print("  ➤  (Press Enter twice when done)\n     ", end="")
    while True:
        line = input()
        if line == "" and lines and lines[-1] == "":
            break
        lines.append(line)
        if line != "":
            print("     ", end="")
    return " ".join(l for l in lines if l).strip()


def _summary_path_for(output_path: str) -> str:
    base, _ext = os.path.splitext(output_path)
    return f"{base}{config.SUMMARY_FILENAME_SUFFIX}"


def _ask_yes_no(question: str, default: bool = False) -> bool:
    suffix = "Y/n" if default else "y/N"
    answer = input(f"{question} ({suffix}): ").strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes"}


def main() -> None:
    print(BANNER)

    parser = argparse.ArgumentParser(
        description="Flutter App Planning Engine — converts a prompt into a full Master Plan JSON"
    )
    parser.add_argument(
        "--prompt", "-p",
        type=str,
        default=None,
        help="App description prompt (if omitted, interactive input is used)",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Output filename (default: outputs/master_plan.json)",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress verbose step-by-step logs",
    )
    parser.add_argument(
        "--chat",
        action="store_true",
        help="Open chat edit mode after generating the plan",
    )
    parser.add_argument(
        "--edit-plan",
        type=str,
        default=None,
        help="Open chat edit mode for an existing plan JSON and exit",
    )
    args = parser.parse_args()

    if args.quiet:
        config.VERBOSE = False

    if args.edit_plan:
        run_chat_editor(args.edit_plan, _summary_path_for(args.edit_plan))
        return

    # ── Get prompt ───────────────────────────────────────────
    prompt = args.prompt
    if not prompt:
        prompt = get_prompt_from_user()

    if not prompt.strip():
        print("\n  ❌  No prompt provided. Exiting.")
        sys.exit(1)

    print(f"\n  📌  Prompt received ({len(prompt)} chars)")
    print(f"  {'─' * 56}")

    # ── Check API key ────────────────────────────────────────
    if config.GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE":
        print("\n  ⚠️   GEMINI_API_KEY is not set!")
        print("  Add it to planning_engine/.env:")
        print("       GEMINI_API_KEY=your_key_here")
        print("  Or set it for this PowerShell session:")
        print("       $env:GEMINI_API_KEY='your_key_here'\n")
        sys.exit(1)

    # ── Run pipeline ─────────────────────────────────────────
    try:
        master_plan = run_planning_pipeline(prompt)
    except RuntimeError as e:
        print(f"\n  ❌  {e}\n")
        sys.exit(1)

    # ── Save output ───────────────────────────────────────────
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    output_path = args.output or os.path.join(
        config.OUTPUT_DIR, config.FINAL_PLAN_FILENAME
    )
    master_plan.save(output_path)
    summary_path = _summary_path_for(output_path)
    plan_dict = master_plan.to_dict()
    save_summary(plan_dict, summary_path)

    # ── Summary ───────────────────────────────────────────────
    print_concise_summary(plan_dict)

    print(f"\n  📁  Full JSON saved to: {output_path}")
    print(f"  📝  Short summary saved to: {summary_path}")
    print(f"  🧮  Usage log saved to: {os.path.join(config.COST_LOG_DIR, config.COST_LOG_FILENAME)}\n")

    should_chat = args.chat
    if not should_chat and not args.prompt and sys.stdin.isatty():
        should_chat = _ask_yes_no("  Open chat edit mode now")

    if should_chat:
        run_chat_editor(output_path, summary_path)


if __name__ == "__main__":
    main()
