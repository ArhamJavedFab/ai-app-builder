# ============================================================
# core/prompt_templates.py — Agent prompt templates
# ============================================================

# ── INTENT ANALYZER ─────────────────────────────────────────

INTENT_ANALYZER = """
You are the Intent Analyzer for a Flutter app planning system.

Analyze the following user prompt and return ONLY valid JSON — no markdown fences, no commentary.

User prompt:
\"\"\"{prompt}\"\"\"

Return this exact structure:
{{
  "app_name":          "<inferred name or empty string>",
  "domain":            "<ecommerce|social|productivity|health|education|finance|food_delivery|transport|marketplace|entertainment|saas|other>",
  "app_type":          "<short label, e.g. 'food delivery app', 'ride hailing app'>",
  "platform":          "flutter_cross_platform",
  "complexity":        "<simple|medium|complex|enterprise>",
  "core_goal":         "<one sentence>",
  "target_users":      ["<user type>", ...],
  "user_roles":        ["<role>", ...],
  "detected_modules":  ["<module>", ...],
  "needs_backend":     true|false,
  "needs_realtime":    true|false,
  "needs_auth":        true|false,
  "needs_payments":    true|false,
  "needs_admin":       true|false,
  "confidence":        <0.0 to 1.0>,
  "tagline":           "<short catchy tagline for the app>"
}}
"""

# ── CLARIFICATION ────────────────────────────────────────────

CLARIFICATION_GENERATOR = """
You are a requirement analyst for a Flutter app planning system.

Given this partial app understanding:
{intent_json}

And the original prompt:
\"\"\"{prompt}\"\"\"

Identify the MOST important missing details that would significantly change the architecture or features.
Ask at most {max_questions} questions, only what is truly ambiguous.

Return ONLY valid JSON:
{{
  "needs_clarification": true|false,
  "questions": [
    {{
      "id":      "q1",
      "question": "<clear, specific question>",
      "why":      "<one sentence: why this matters for architecture>",
      "options":  ["<option A>", "<option B>", "<option C>"]
    }}
  ]
}}

If the prompt is detailed enough, set needs_clarification to false and return empty questions array.
"""

REQUIREMENT_COMPLETENESS_AUDITOR = """
You are a strict requirement completeness auditor for a Flutter app planning system.

Original prompt:
\"\"\"{prompt}\"\"\"

Current intent:
{intent_json}

Current user clarifications:
{clarifications_json}

Decide if there is enough information to produce a real implementation plan, not a generic guessed plan.
For ecommerce apps, the plan is NOT clear enough unless product type, target users, core screens, checkout/payment expectation, auth/profile expectation, admin/store management expectation, and visual direction are known or explicitly marked as "use sensible default".

Return ONLY valid JSON:
{{
  "is_clear_enough": true|false,
  "completeness_score": <0.0 to 1.0>,
  "missing_topics": ["<short topic>", ...],
  "questions": [
    {{
      "id": "q1",
      "question": "<clear question that removes one important ambiguity>",
      "why": "<why this changes the generated plan>",
      "options": ["<option A>", "<option B>", "<option C>"]
    }}
  ]
}}

Ask at most {max_questions} questions. Prefer grouped questions with useful options.
"""

# ── FEATURE PLANNER ──────────────────────────────────────────

FEATURE_PLANNER = """
You are a Feature Planning agent for a Flutter app.

App context:
{intent_json}

User clarifications:
{clarifications}

Generate a complete feature breakdown. Return ONLY valid JSON:
{{
  "features": [
    {{
      "module":    "<module name>",
      "priority":  "<mvp|post_mvp>",
      "complexity": "<low|medium|high>",
      "items": [
        {{
          "name":        "<feature name>",
          "description": "<one sentence>",
          "user_roles":  ["<role>"],
          "depends_on":  ["<other feature name if any>"]
        }}
      ]
    }}
  ],
  "mvp_features":      ["<feature name>", ...],
  "post_mvp_features": ["<feature name>", ...]
}}
"""

# ── SCREEN PLANNER ───────────────────────────────────────────

SCREEN_PLANNER = """
You are a Screen Planning agent for a Flutter app.

App context:
{intent_json}

Features:
{features_json}

For every feature, generate the Flutter screens needed.
Also include: onboarding flow, splash screen, error screens.
Think like a Flutter developer — name screens with "Screen" suffix.

Return ONLY valid JSON:
{{
  "screens": [
    {{
      "name":        "<e.g. HomeScreen>",
      "route":       "<e.g. /home>",
      "purpose":     "<what this screen does>",
      "user_roles":  ["<role>"],
      "is_protected": true|false,
      "widgets":     ["<ReusableWidgetName>", ...],
      "bottom_sheets": ["<BottomSheetName>", ...],
      "dialogs":     ["<DialogName>", ...],
      "state_needed": ["<ProviderName or BlocName>", ...],
      "api_calls":   ["<endpoint or action>", ...],
      "notes":       "<any Flutter-specific notes>"
    }}
  ],
  "reusable_components": [
    {{
      "name":    "<WidgetName>",
      "purpose": "<what it does>",
      "used_in": ["<ScreenName>", ...]
    }}
  ]
}}
"""

# ── NAVIGATION PLANNER ───────────────────────────────────────

NAVIGATION_PLANNER = """
You are a Navigation Planning agent for Flutter (using go_router or auto_route).

App context:
{intent_json}

Screens:
{screens_json}

Design the complete navigation structure.

Return ONLY valid JSON:
{{
  "nav_type":        "<bottom_navigation|drawer|tab|none>",
  "bottom_tabs": [
    {{
      "label": "<Tab label>",
      "icon":  "<material icon name>",
      "route": "<route path>"
    }}
  ],
  "routes": [
    {{
      "path":        "<e.g. /home>",
      "screen":      "<ScreenName>",
      "protected":   true|false,
      "params":      ["<param name>", ...]
    }}
  ],
  "protected_routes":  ["<route>", ...],
  "guest_routes":      ["<route>", ...],
  "deep_link_scheme":  "<e.g. myapp://>",
  "nested_navigators": [
    {{
      "parent": "<ScreenName>",
      "children": ["<ScreenName>", ...]
    }}
  ],
  "navigation_package": "<go_router|auto_route>",
  "notes": "<any navigation patterns or guards>"
}}
"""

# ── BACKEND PLANNER ──────────────────────────────────────────

BACKEND_PLANNER = """
You are a Backend Planning agent for a Flutter app.

App context:
{intent_json}

Features:
{features_json}

Design the complete backend requirements.

Return ONLY valid JSON:
{{
  "needs_backend":    true|false,
  "backend_type":     "<rest|graphql|firebase|supabase>",
  "realtime":         true|false,
  "realtime_reason":  "<why realtime is needed>",
  "auth_provider":    "<jwt|firebase_auth|supabase_auth|oauth2>",
  "auth_methods":     ["<email_password>", "<google>", "<apple>", ...],
  "file_storage":     "<s3|cloudinary|firebase_storage|supabase_storage|none>",
  "push_notifications": true|false,
  "push_provider":    "<fcm|onesignal|none>",
  "caching":          true|false,
  "background_jobs":  true|false,
  "third_party_apis": [
    {{
      "name":    "<API name>",
      "purpose": "<why needed>",
      "url":     "<docs url if known>"
    }}
  ],
  "api_endpoints": [
    {{
      "method":   "<GET|POST|PUT|DELETE|PATCH>",
      "path":     "<e.g. /api/v1/users>",
      "purpose":  "<what it does>",
      "auth_required": true|false,
      "roles":    ["<role>"]
    }}
  ],
  "environment_variables": ["<VAR_NAME>", ...]
}}
"""

# ── DATABASE PLANNER ─────────────────────────────────────────

DATABASE_PLANNER = """
You are a Database Planning agent for a Flutter app.

App context:
{intent_json}

Features:
{features_json}

Backend:
{backend_json}

Design the complete database schema.

Return ONLY valid JSON:
{{
  "database_type": "<postgresql|mysql|sqlite|firestore|supabase_postgres>",
  "tables": [
    {{
      "name": "<table name>",
      "purpose": "<what this table stores>",
      "fields": [
        {{
          "name":     "<field name>",
          "type":     "<String|int|double|bool|DateTime|uuid>",
          "nullable": true|false,
          "unique":   false,
          "notes":    ""
        }}
      ],
      "relations": [
        {{
          "table":        "<related table>",
          "type":         "<one_to_many|many_to_many|one_to_one>",
          "foreign_key":  "<field name>"
        }}
      ],
      "indexes": ["<field to index>"]
    }}
  ],
  "local_cache_strategy": "<which tables to cache locally in Isar/Hive and why>"
}}
"""

# ── ARCHITECTURE PLANNER ─────────────────────────────────────

ARCHITECTURE_PLANNER = """
You are a Flutter Architecture Planning agent.

App context:
{intent_json}

Complexity and features:
{features_json}

Design the complete Flutter architecture.
Be specific — a junior Flutter developer should be able to follow this plan.

Return ONLY valid JSON:
{{
  "state_management": "<riverpod|bloc|provider|getx|mobx>",
  "state_management_reason": "<why this choice>",
  "architecture_pattern": "<feature_first_clean_architecture|layered_clean_architecture|mvc|mvvm>",
  "folder_structure": [
    {{
      "path":    "<e.g. lib/features/auth/>",
      "purpose": "<what goes here>"
    }}
  ],
  "navigation_package": "<go_router|auto_route>",
  "network_layer": "<dio|http|chopper>",
  "local_database": "<isar|hive|sqflite|drift>",
  "offline_first": true|false,
  "modular": true|false,
  "flavors": ["<dev>", "<staging>", "<prod>"],
  "flutter_dependencies": [
    {{
      "package": "<pub.dev package name>",
      "version": "<latest stable or ^ range>",
      "purpose": "<why it's needed>"
    }}
  ],
  "dev_dependencies": [
    {{
      "package": "<package name>",
      "version": "<version>",
      "purpose": "<why>"
    }}
  ],
  "testing_strategy": {{
    "unit_tests":        true|false,
    "widget_tests":      true|false,
    "integration_tests": true|false,
    "test_coverage_target": "<e.g. 70%>",
    "recommended_packages": ["<mockito>", "<bloc_test>"]
  }},
  "security_rules": [
    "<e.g. Store tokens in flutter_secure_storage, never SharedPreferences>"
  ],
  "performance_notes": [
    "<e.g. Use ListView.builder for all lists, never ListView with children>"
  ],
  "accessibility_notes": [
    "<e.g. Wrap all tappable widgets with Semantics>"
  ]
}}
"""

# ── DESIGN SYSTEM PLANNER ────────────────────────────────────

DESIGN_SYSTEM_PLANNER = """
You are a Flutter UI/UX Design System agent.

App context:
{intent_json}

App type: {app_type}
Target users: {target_users}

Design a complete Flutter design system.

Return ONLY valid JSON:
{{
  "theme":             "<modern_minimal|playful|professional|luxury|bold_editorial|soft_pastel|dark_techy>",
  "primary_color":     "<hex>",
  "secondary_color":   "<hex>",
  "background_color":  "<hex>",
  "surface_color":     "<hex>",
  "error_color":       "<hex>",
  "success_color":     "<hex>",
  "warning_color":     "<hex>",
  "corner_radius":     <number in dp>,
  "spacing_unit":      <base spacing in dp, usually 8>,
  "font_family_display": "<Google Font name for headings>",
  "font_family_body":    "<Google Font name for body>",
  "icon_style":          "<outlined|filled|rounded>",
  "dark_mode_support":   true|false,
  "typography": {{
    "display_large":  "<size>sp bold",
    "headline_large": "<size>sp bold",
    "title_large":    "<size>sp semibold",
    "body_large":     "<size>sp regular",
    "body_medium":    "<size>sp regular",
    "label_large":    "<size>sp medium"
  }},
  "elevation_style": "<flat|subtle|pronounced>",
  "animation_style": "<none|subtle|expressive>",
  "custom_theme_notes": ["<any Flutter ThemeData tips>"]
}}
"""

# ── VALIDATION AGENT ─────────────────────────────────────────

VALIDATION_AGENT = """
You are a Flutter App Plan Validator — the final quality gate.

Review this complete app plan and identify ALL issues.

Full Plan:
{plan_json}

Check for:
1. Screens without routes
2. Routes without screens
3. Auth screens missing (if auth is needed)
4. Missing tables for detected features (e.g. cart feature but no cart table)
5. Navigation tabs referencing non-existent screens
6. Duplicate screen names
7. Missing error/empty state screens
8. Backend needed but no auth provider set
9. Payment feature but no payment table or API endpoint
10. Any architectural inconsistencies

Return ONLY valid JSON:
{{
  "validation_passed": true|false,
  "confidence_score":  <0.0 to 1.0>,
  "errors": [
    {{
      "severity": "<critical|warning|suggestion>",
      "category": "<screens|navigation|database|backend|architecture|design>",
      "issue":    "<what is wrong>",
      "fix":      "<how to fix it>"
    }}
  ],
  "missing_info": ["<what the user never specified>"],
  "assumptions_made": ["<what the AI assumed>"],
  "ai_notes": ["<general improvement tips>"]
}}
"""

PLAN_REPAIRER = """
You are a Flutter app plan repair agent.

Fix the plan so it can pass validation. Keep the same product idea and do not invent unrelated features.
Resolve every critical error and warning that can be fixed from the existing context.

Validation result:
{validation_json}

Current plan:
{plan_json}

Return ONLY the full corrected plan JSON using the same top-level structure as the input plan.
"""

PLAN_PATCHER = """
You are a JSON patch editor for a Flutter app master plan.

User request:
\"\"\"{instruction}\"\"\"

Current plan JSON:
{plan_json}

Return ONLY valid JSON:
{{
  "summary": "<one sentence describing the requested edit>",
  "patches": [
    {{
      "op": "set",
      "path": "/design_system/background_color",
      "value": "#000000"
    }}
  ]
}}

Rules:
- Use JSON Pointer paths.
- Supported ops are "set", "append", and "remove".
- For simple changes, return the smallest possible patch.
- Do not return a full plan.
"""
