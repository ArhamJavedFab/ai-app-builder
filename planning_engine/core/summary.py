# ============================================================
# core/summary.py — Rich plan card (Lovable-style terminal output)
# ============================================================

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# ─────────────────────────────────────────────────────────────
# DATA HELPERS
# ─────────────────────────────────────────────────────────────

def _feature_names(plan: dict, limit: int = 6) -> list[str]:
    out = []
    for module in plan.get("features", []):
        for item in module.get("items", []):
            if item.get("name"):
                out.append(str(item["name"]))
            if len(out) >= limit:
                return out
    return out


def _mvp_screen_routes(plan: dict) -> list[dict]:
    """Return screens that are MVP + protected or guest, with route + purpose."""
    screens = plan.get("screens", [])
    result  = []
    for s in screens:
        if s.get("name", "").lower() in ("splashscreen", "errorscreen"):
            continue
        result.append({
            "name":    s.get("name", ""),
            "route":   s.get("route", ""),
            "purpose": s.get("purpose", ""),
        })
    return result[:10]


def _user_flow_names(plan: dict) -> list[str]:
    return [f.get("name", "") for f in plan.get("user_flows", []) if f.get("name")]


def _tech_badges(plan: dict) -> list[str]:
    arch    = plan.get("flutter_architecture", {})
    backend = plan.get("backend", {})
    badges  = []
    if arch.get("state_management"):
        badges.append(arch["state_management"].capitalize())
    if arch.get("navigation_package"):
        badges.append(arch["navigation_package"])
    if backend.get("backend_type"):
        badges.append(backend["backend_type"].replace("_", " ").title())
    if backend.get("auth_provider"):
        badges.append(backend["auth_provider"].replace("_", " ").title())
    if arch.get("architecture_pattern"):
        label = arch["architecture_pattern"].replace("_", " ").title()
        badges.append(label[:28])
    return badges[:6]


def _color_swatch(hex_color: str) -> str:
    """Return a simple text swatch since terminals can't render real color blocks."""
    return f"█ {hex_color}" if hex_color else ""


def _scope_label(plan: dict) -> str:
    mvp = plan.get("mvp_features", [])
    post = plan.get("post_mvp_features", [])
    return f"{len(mvp)} MVP features · {len(post)} planned for later"


# ─────────────────────────────────────────────────────────────
# RICH PLAN CARD
# ─────────────────────────────────────────────────────────────

def print_plan_card(plan: dict) -> None:
    """
    Print a Lovable-style rich plan card to the terminal.

    Sections (mirrors Lovable's UI):
      ┌─ App header (name, tagline, summary)
      ├─ What I inferred  (auto-answered facts)
      ├─ Screens & Routes
      ├─ User Flows
      ├─ Style direction  (colors, fonts, theme)
      ├─ Scope of v1      (MVP vs later)
      ├─ Technical notes  (state, arch, backend)
      └─ Quality signal   (confidence, warnings)
    """
    W = 62   # card width

    def rule(char: str = "─") -> None:
        print("  " + char * W)

    def row(label: str, value: str, indent: int = 0) -> None:
        pad = "  " * indent
        print(f"  {pad}{label:<18}{value}")

    def section(title: str) -> None:
        print()
        rule()
        print(f"  ◈  {title.upper()}")
        rule()

    app_name = plan.get("app_name") or "Your App"
    tagline  = plan.get("tagline") or ""
    summary  = plan.get("summary") or ""
    design   = plan.get("design_system", {})
    arch     = plan.get("flutter_architecture", {})
    backend  = plan.get("backend", {})
    quality  = {"passed": plan.get("validation_passed", False),
                "score":  plan.get("confidence_score", 0.0),
                "warns":  plan.get("validation_warnings", [])}

    # ── Header ───────────────────────────────────────────────
    print()
    print("  " + "═" * W)
    print(f"  ✦  {app_name}")
    if tagline:
        print(f"     {tagline}")
    print("  " + "═" * W)
    if summary:
        # Word-wrap summary at W-4 chars
        words, line = summary.split(), ""
        for word in words:
            if len(line) + len(word) + 1 > W - 4:
                print(f"  {line}")
                line = word
            else:
                line = f"{line} {word}".strip()
        if line:
            print(f"  {line}")

    # ── What the AI inferred ─────────────────────────────────
    users     = plan.get("target_users", [])
    app_type  = plan.get("app_type", "")
    user_roles = plan.get("user_roles", [])
    if users or app_type:
        section("What I understood from your idea")
        if app_type:
            row("Type", app_type)
        if users:
            row("For", ", ".join(users[:4]))
        if user_roles:
            row("Roles", ", ".join(user_roles[:4]))
        notes = plan.get("assumptions_made", [])
        if notes:
            print(f"\n  Assumed:")
            for n in notes[:3]:
                print(f"   · {n}")

    # ── Screens & Routes ─────────────────────────────────────
    screens = _mvp_screen_routes(plan)
    if screens:
        section("Screens & Routes")
        for s in screens:
            route   = s["route"] or "(no route)"
            purpose = s["purpose"]
            # Truncate purpose to fit on one line
            max_p = W - len(route) - 6
            if len(purpose) > max_p:
                purpose = purpose[:max_p - 1] + "…"
            print(f"  {route:<24}  {purpose}")

    # ── User Flows ───────────────────────────────────────────
    flows = plan.get("user_flows", [])
    if flows:
        section("User Flows")
        for flow in flows[:6]:
            name  = flow.get("name", "")
            steps = flow.get("steps", [])
            trigger = flow.get("trigger", "")
            print(f"  ▸ {name}")
            if trigger:
                print(f"    Starts: {trigger}")
            if steps:
                print(f"    Steps:  {' → '.join(str(s) for s in steps[:6])}")

    # ── Style Direction ──────────────────────────────────────
    section("Style Direction")
    theme = design.get("theme", "")
    if theme:
        print(f"  Theme       {theme.replace('_', ' ').title()}")

    primary = design.get("primary_color", "")
    bg      = design.get("background_color", "")
    surface = design.get("surface_color", "")
    if primary or bg:
        print(f"\n  Palette")
        if primary: print(f"   Primary    {_color_swatch(primary)}")
        if bg:      print(f"   Background {_color_swatch(bg)}")
        if surface: print(f"   Surface    {_color_swatch(surface)}")

    font_d = design.get("font_family_display", "")
    font_b = design.get("font_family_body", "")
    if font_d or font_b:
        print(f"\n  Typography")
        if font_d: print(f"   Display    {font_d}")
        if font_b: print(f"   Body       {font_b}")

    corner = design.get("corner_radius")
    anim   = design.get("animation_style", "")
    elev   = design.get("elevation_style", "")
    dark   = design.get("dark_mode_support", False)
    print(f"\n  Details")
    if corner:  print(f"   Radius     {corner}dp")
    if anim:    print(f"   Motion     {anim.title()}")
    if elev:    print(f"   Elevation  {elev.title()}")
    print(f"   Dark mode  {'Yes' if dark else 'No'}")

    custom = design.get("custom_theme_notes", [])
    if custom:
        print(f"\n  Theme notes")
        for note in custom[:3]:
            print(f"   · {note}")

    # ── Scope of v1 ──────────────────────────────────────────
    section("Scope of v1")
    mvp_features  = plan.get("mvp_features", [])
    post_features = plan.get("post_mvp_features", [])

    if mvp_features:
        print(f"  Included in v1:")
        for f in mvp_features[:8]:
            print(f"   ✓ {f}")

    if post_features:
        print(f"\n  Planned for later:")
        for f in post_features[:5]:
            print(f"   ○ {f}")

    # ── Technical Notes ──────────────────────────────────────
    section("Technical Notes")

    state   = arch.get("state_management", "")
    pattern = arch.get("architecture_pattern", "").replace("_", " ").title()
    nav_pkg = arch.get("navigation_package", "")
    net     = arch.get("network_layer", "")
    cart_s  = arch.get("cart_strategy", "")

    if state:   print(f"  State management   {state.capitalize()}")
    if pattern: print(f"  Architecture       {pattern}")
    if nav_pkg: print(f"  Navigation         {nav_pkg}")
    if net:     print(f"  Network layer      {net}")
    if cart_s:  print(f"  Cart strategy      {cart_s}")

    # Firebase services
    fb_services = backend.get("firebase_services", [])
    if fb_services:
        print(f"\n  Firebase services")
        for svc in fb_services:
            print(f"   · {svc}")

    # Collections
    collections = backend.get("firestore_collections") or [
        t.get("name") for t in plan.get("database_tables", []) if t.get("name")
    ]
    if collections:
        print(f"\n  Firestore collections")
        for c in collections[:8]:
            print(f"   · {c}")

    # Dependencies count
    deps = plan.get("flutter_dependencies", [])
    if deps:
        print(f"\n  Flutter packages    {len(deps)} dependencies")
        for d in deps[:5]:
            print(f"   · {d.get('package','')}  {d.get('version','')}")
        if len(deps) > 5:
            print(f"   … and {len(deps) - 5} more")

    # ── Quality Signal ───────────────────────────────────────
    section("Quality Signal")
    status = "✅ Passed" if quality["passed"] else "⚠️  Has warnings"
    score  = quality["score"]
    print(f"  Validation     {status}")
    print(f"  Confidence     {score:.0%}")

    warns = quality["warns"]
    if warns:
        print(f"\n  Warnings ({len(warns)}):")
        for w in warns[:4]:
            print(f"   · {w}")

    missing = plan.get("missing_info", [])
    if missing:
        print(f"\n  Missing info:")
        for m in missing[:3]:
            print(f"   ? {m}")

    ai_notes = plan.get("ai_notes", [])
    if ai_notes:
        print(f"\n  AI suggestions:")
        for n in ai_notes[:3]:
            print(f"   ★ {n}")

    # ── Footer ───────────────────────────────────────────────
    print()
    rule("═")
    screens_count = len(plan.get("screens", []))
    tables_count  = len(plan.get("database_tables", []))
    flows_count   = len(flows)
    print(f"  {screens_count} screens · {tables_count} data collections · {flows_count} user flows")
    rule("═")
    print()


# ─────────────────────────────────────────────────────────────
# MACHINE-READABLE SUMMARY  (saved as _summary.json)
# ─────────────────────────────────────────────────────────────

def build_concise_summary(plan: dict[str, Any]) -> dict[str, Any]:
    features  = plan.get("features", [])
    feature_names = [
        item.get("name", "")
        for module in features
        for item in module.get("items", [])
        if item.get("name")
    ]
    screens  = plan.get("screens", [])
    backend  = plan.get("backend", {})
    design   = plan.get("design_system", {})
    arch     = plan.get("flutter_architecture", {})

    return {
        "app_name":     plan.get("app_name") or "(unnamed)",
        "app_type":     plan.get("app_type", ""),
        "tagline":      plan.get("tagline", ""),
        "summary":      plan.get("summary", ""),
        "target_users": plan.get("target_users", []),
        "user_roles":   plan.get("user_roles", []),
        "top_features": feature_names[:10],
        "mvp_features": plan.get("mvp_features", [])[:8],
        "post_mvp_features": plan.get("post_mvp_features", [])[:5],
        "main_screens": [
            {"name": s.get("name",""), "route": s.get("route",""), "purpose": s.get("purpose","")}
            for s in screens[:12]
        ],
        "user_flows": [
            {"id": f.get("id",""), "name": f.get("name",""), "steps": f.get("steps",[])}
            for f in plan.get("user_flows", [])
        ],
        "backend": {
            "type":        backend.get("backend_type", ""),
            "auth":        backend.get("auth_provider", ""),
            "services":    backend.get("firebase_services", []),
            "collections": backend.get("firestore_collections", []),
            "payment":     backend.get("payment_method", ""),
        },
        "architecture": {
            "state_management": arch.get("state_management", ""),
            "pattern":          arch.get("architecture_pattern", ""),
            "navigation":       arch.get("navigation_package", ""),
            "cart_strategy":    arch.get("cart_strategy", ""),
        },
        "design": {
            "theme":            design.get("theme", ""),
            "primary_color":    design.get("primary_color", ""),
            "background_color": design.get("background_color", ""),
            "fonts": [design.get("font_family_display",""), design.get("font_family_body","")],
            "dark_mode":        design.get("dark_mode_support", False),
        },
        "quality": {
            "validation_passed": plan.get("validation_passed", False),
            "confidence":        plan.get("confidence_score", 0.0),
            "warnings":          plan.get("validation_warnings", [])[:5],
            "missing_info":      plan.get("missing_info", [])[:3],
            "ai_notes":          plan.get("ai_notes", [])[:3],
        },
    }


def save_summary(plan: dict[str, Any], path: str | Path) -> None:
    summary = build_concise_summary(plan)
    Path(path).write_text(json.dumps(summary, indent=2), encoding="utf-8")


def print_concise_summary(plan: dict[str, Any]) -> None:
    """Called from main.py — renders the full rich plan card."""
    print_plan_card(plan)
