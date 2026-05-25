# ============================================================
# core/schema.py — Master Plan schema + helpers
# ============================================================

from dataclasses import dataclass, field, asdict
from typing import Any
import json


# ── Nested structures ─────────────────────────────────────────

@dataclass
class DesignSystem:
    theme: str                  = "modern_minimal"
    primary_color: str          = "#4F46E5"
    secondary_color: str        = "#06B6D4"
    background_color: str       = "#FFFFFF"
    surface_color: str          = "#F9FAFB"
    error_color: str            = "#EF4444"
    corner_radius: int          = 12
    spacing_unit: int           = 8
    font_family_display: str    = "Poppins"
    font_family_body: str       = "Inter"
    icon_style: str             = "outlined"          # outlined | filled | rounded
    dark_mode_support: bool     = True
    custom_theme_notes: list    = field(default_factory=list)


@dataclass
class FlutterArchitecture:
    state_management: str       = "riverpod"          # riverpod | bloc | provider | getx
    architecture_pattern: str   = "feature_first_clean_architecture"
    navigation_package: str     = "go_router"
    network_layer: str          = "firebase_sdk"
    local_database: str         = "firestore_offline_cache"
    offline_first: bool         = True
    modular: bool               = True
    flavors: list               = field(default_factory=list)   # dev / staging / prod


@dataclass
class Screen:
    id: str                     = ""
    name: str                   = ""
    route: str                  = ""
    purpose: str                = ""
    user_roles: list            = field(default_factory=list)
    is_protected: bool          = True
    widgets: list               = field(default_factory=list)   # reusable widget names
    bottom_sheets: list         = field(default_factory=list)
    dialogs: list               = field(default_factory=list)
    state_needed: list          = field(default_factory=list)   # providers / blocs
    api_calls: list             = field(default_factory=list)
    notes: str                  = ""


@dataclass
class NavigationMap:
    initial_route: str          = ""                  # e.g. /splash
    redirects: list             = field(default_factory=list)  # {from, when, to}
    nav_type: str               = "bottom_navigation"  # bottom | drawer | tab | none
    bottom_tabs: list           = field(default_factory=list)
    routes: list                = field(default_factory=list)
    protected_routes: list      = field(default_factory=list)
    guest_routes: list          = field(default_factory=list)
    deep_link_scheme: str       = ""
    nested_navigators: list     = field(default_factory=list)
    navigation_package: str     = "go_router"


@dataclass
class DatabaseTable:
    name: str                   = ""
    fields: list                = field(default_factory=list)   # {name, type, nullable}
    relations: list             = field(default_factory=list)   # {table, type: FK/M2M}
    indexes: list               = field(default_factory=list)


@dataclass
class BackendRequirements:
    needs_backend: bool         = True
    backend_type: str           = "firebase"
    realtime: bool              = False
    auth_provider: str          = "firebase_auth"
    file_storage: str           = "none"
    push_notifications: bool    = False
    third_party_apis: list      = field(default_factory=list)
    caching: bool               = False
    background_jobs: bool       = False


@dataclass
class Monetization:
    model: str                  = "none"              # none | freemium | subscription | iap | ads
    subscription_tiers: list    = field(default_factory=list)
    in_app_purchases: list      = field(default_factory=list)
    notes: str                  = ""


# ── Master Plan ───────────────────────────────────────────────

@dataclass
class MasterPlan:
    # ── Plan contract (stable identity across phases)
    plan_version: str                   = "1.1"
    project_id: str                     = ""
    updated_at: str                     = ""
    data_tier: str                      = ""          # local_only | firebase
    storage_profile: str              = ""          # alarm | notes | tasks | media | generic | firebase

    # ── Identity
    app_name: str                       = ""
    app_type: str                       = ""          # ecommerce | social | productivity | etc.
    platform: str                       = "flutter_cross_platform"
    summary: str                        = ""
    tagline: str                        = ""

    # ── Users
    target_users: list                  = field(default_factory=list)
    user_roles: list                    = field(default_factory=list)   # admin, customer, driver…

    # ── Features
    features: list                      = field(default_factory=list)   # {module, items[], priority}
    mvp_features: list                  = field(default_factory=list)
    post_mvp_features: list             = field(default_factory=list)
    mvp_feature_ids: list               = field(default_factory=list)
    post_mvp_feature_ids: list          = field(default_factory=list)
    user_flows: list                    = field(default_factory=list)
    reusable_components: list           = field(default_factory=list)

    # ── Screens
    screens: list[dict]                 = field(default_factory=list)   # Screen dicts

    # ── Navigation
    navigation: dict                    = field(default_factory=dict)   # NavigationMap dict

    # ── Backend
    backend: dict                       = field(default_factory=dict)   # BackendRequirements dict

    # ── Database
    database_tables: list[dict]         = field(default_factory=list)   # DatabaseTable dicts

    # ── Flutter Architecture
    flutter_architecture: dict          = field(default_factory=dict)   # FlutterArchitecture dict

    # ── Design
    design_system: dict                 = field(default_factory=dict)   # DesignSystem dict

    # ── Dependencies
    flutter_dependencies: list          = field(default_factory=list)   # {package, version, reason}
    dev_dependencies: list              = field(default_factory=list)

    # ── Quality
    security_rules: list                = field(default_factory=list)
    edge_cases: list                    = field(default_factory=list)
    accessibility_notes: list           = field(default_factory=list)
    performance_notes: list             = field(default_factory=list)
    testing_strategy: dict              = field(default_factory=dict)

    # ── Business
    monetization: dict                  = field(default_factory=dict)   # Monetization dict
    analytics_events: list              = field(default_factory=list)

    # ── AI Meta
    confidence_score: float             = 0.0          # 0.0 – 1.0
    missing_info: list                  = field(default_factory=list)
    assumptions_made: list              = field(default_factory=list)
    ai_notes: list                      = field(default_factory=list)
    validation_warnings: list           = field(default_factory=list)
    validation_passed: bool             = False

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def save(self, path: str) -> None:
        from core.plan_ids import normalize_plan_ids

        payload = normalize_plan_ids(self.to_dict())
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps(payload, indent=2))
        print(f"  ✅  Plan saved → {path}")


def empty_plan() -> MasterPlan:
    return MasterPlan()
