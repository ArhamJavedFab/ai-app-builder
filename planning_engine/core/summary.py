from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_concise_summary(plan: dict[str, Any]) -> dict[str, Any]:
    features = plan.get("features", [])
    feature_names = [
        item.get("name", "")
        for module in features
        for item in module.get("items", [])
        if item.get("name")
    ]
    screens = plan.get("screens", [])
    backend = plan.get("backend", {})
    design = plan.get("design_system", {})
    architecture = plan.get("flutter_architecture", {})

    return {
        "app_name": plan.get("app_name") or "(unnamed)",
        "app_type": plan.get("app_type", ""),
        "summary": plan.get("summary", ""),
        "target_users": plan.get("target_users", []),
        "top_features": feature_names[:10],
        "main_screens": [s.get("name", "") for s in screens[:12]],
        "backend": {
            "type": backend.get("backend_type", ""),
            "auth": backend.get("auth_provider", ""),
            "api_endpoints": len(backend.get("api_endpoints", [])),
        },
        "data": {
            "tables": [t.get("name", "") for t in plan.get("database_tables", [])],
        },
        "architecture": {
            "state_management": architecture.get("state_management", ""),
            "pattern": architecture.get("architecture_pattern", ""),
            "navigation": architecture.get("navigation_package", ""),
        },
        "design": {
            "theme": design.get("theme", ""),
            "primary_color": design.get("primary_color", ""),
            "background_color": design.get("background_color", ""),
            "fonts": [
                design.get("font_family_display", ""),
                design.get("font_family_body", ""),
            ],
        },
        "quality": {
            "validation_passed": plan.get("validation_passed", False),
            "confidence": plan.get("confidence_score", 0.0),
            "warnings": plan.get("validation_warnings", [])[:5],
        },
    }


def save_summary(plan: dict[str, Any], path: str | Path) -> None:
    summary = build_concise_summary(plan)
    Path(path).write_text(json.dumps(summary, indent=2), encoding="utf-8")


def print_concise_summary(plan: dict[str, Any]) -> None:
    summary = build_concise_summary(plan)
    quality = summary["quality"]

    print("\n  PLAN SUMMARY")
    print("  " + "-" * 56)
    print(f"  App:          {summary['app_name']}")
    print(f"  Type:         {summary['app_type']}")
    print(f"  Users:        {', '.join(summary['target_users'][:4])}")
    print(f"  Features:     {len(summary['top_features'])} highlighted")
    print(f"  Screens:      {len(summary['main_screens'])} shown")
    print(f"  Backend:      {summary['backend']['type']} / {summary['backend']['auth']}")
    print(f"  Database:     {len(summary['data']['tables'])} tables")
    print(
        "  Architecture: "
        f"{summary['architecture']['state_management']} + "
        f"{summary['architecture']['pattern']}"
    )
    print(
        "  Design:       "
        f"{summary['design']['theme']} | "
        f"{summary['design']['primary_color']} on "
        f"{summary['design']['background_color']}"
    )
    print(f"  Confidence:   {quality['confidence']:.0%}")
    print(f"  Validated:    {'Yes' if quality['validation_passed'] else 'No'}")

    if summary["top_features"]:
        print("\n  Key features:")
        for name in summary["top_features"][:6]:
            print(f"   - {name}")

    if quality["warnings"]:
        print("\n  Validation notes:")
        for warning in quality["warnings"]:
            print(f"   - {warning}")

