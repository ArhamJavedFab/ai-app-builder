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
    args = parser.parse_args()

    if args.quiet:
        config.VERBOSE = False

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

    # ── Summary ───────────────────────────────────────────────
    plan_dict = master_plan.to_dict()

    print(f"\n  📊  PLAN SUMMARY")
    print(f"  {'─' * 56}")
    print(f"  App Name:        {plan_dict['app_name'] or '(unnamed)'}")
    print(f"  App Type:        {plan_dict['app_type']}")
    print(f"  Screens:         {len(plan_dict['screens'])}")
    print(f"  Features:        {sum(len(m.get('items',[])) for m in plan_dict['features'])}")
    print(f"  DB Tables:       {len(plan_dict['database_tables'])}")
    print(f"  Dependencies:    {len(plan_dict['flutter_dependencies'])}")
    print(f"  State Mgmt:      {plan_dict['flutter_architecture'].get('state_management','')}")
    print(f"  Architecture:    {plan_dict['flutter_architecture'].get('architecture_pattern','')}")
    print(f"  Confidence:      {plan_dict['confidence_score']:.0%}")
    print(f"  Validated:       {'✅ Yes' if plan_dict['validation_passed'] else '❌ No (see warnings)'}")
    print(f"  {'─' * 56}")

    warnings = plan_dict.get("validation_warnings", [])
    if warnings:
        print(f"\n  ⚠️   Warnings ({len(warnings)}):")
        for w in warnings:
            print(f"       • {w}")

    missing = plan_dict.get("missing_info", [])
    if missing:
        print(f"\n  ℹ️   Missing info (consider a follow-up run):")
        for m in missing:
            print(f"       • {m}")

    print(f"\n  📁  Output saved to: {output_path}\n")


if __name__ == "__main__":
    main()
