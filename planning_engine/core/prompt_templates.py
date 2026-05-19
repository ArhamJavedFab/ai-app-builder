# ============================================================
# core/prompt_templates.py â€” Agent prompt templates
# ============================================================

# â”€â”€ INTENT ANALYZER â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

INTENT_ANALYZER = """
You are the Intent Analyzer for a Flutter app planning system.

Analyze the following user prompt and return ONLY valid JSON â€” no markdown fences, no commentary.

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

Identify only missing details that change screens or data.
Ask at most {max_questions} short questions.
Each question must ask one thing only.
Put short hints in examples, shown as "(e.g. ...)".

Return ONLY valid JSON:
{{
  "needs_clarification": true|false,
  "questions": [
    {{
      "id":      "q1",
      "question": "<short question>",
      "examples": ["<short example answer>", "<another short example answer>"]
    }}
  ]
}}

If the prompt is detailed enough, set needs_clarification to false and return empty questions array.
"""

# ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# ///////////////////////////////////////////    STARTUP_QUESTION_GENERATOR    ///////////////////////////////////////////
STARTUP_QUESTION_GENERATOR = """
You are generating the first required clarification questions for a Flutter app planning CLI.

User prompt:
\"\"\"{prompt}\"\"\"

Current intent:
{intent_json}

Suggested app name:
{suggested_name}

Return ONLY valid JSON:
{{
  "questions": [
    {{
      "id": "app_name",
      "question": "What is the app name?",
      "examples": ["{suggested_name}"],
      "default_answer": "{suggested_name}"
    }},
    {{
      "id": "target_users",
      "question": "Who will use this app?",
      "examples": ["<domain-specific user group>", "<another domain-specific user group>"]
    }},
    {{
      "id": "mvp_scope",
      "question": "What features come first?",
      "examples": ["<domain-specific MVP scope>", "use sensible defaults"]
    }},
    {{
      "id": "management_scope",
      "question": "Is this personal or shared?",
      "examples": ["<domain-specific answer>", "use sensible defaults"]
    }}
  ]
}}

Rules:
- The examples MUST match the user's app idea and domain.
- Do not use generic school, employee, manager, ecommerce, or attendance examples unless the user prompt is actually about that domain.
- Use full-sentence questions, 5 to 6 words.
- Each question asks exactly one thing.
- Do not include a why field.
- Keep exactly these 4 ids: app_name, target_users, mvp_scope, management_scope.
- The first question must include default_answer.
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
For ecommerce apps, the plan is NOT clear enough unless product type, target users, core screens,
checkout/payment expectation, auth/profile expectation, admin/store management expectation,
and visual direction are known or explicitly marked as "use sensible default".

Return ONLY valid JSON:
{{
  "is_clear_enough": true|false,
  "completeness_score": <0.0 to 1.0>,
  "missing_topics": ["<short topic>", ...],
  "questions": [
    {{
      "id": "q1",
      "question": "<short question that asks one thing>",
      "examples": ["<short example answer>", "<another short example answer>"]
    }}
  ]
}}

Ask at most {max_questions} questions.
Each question must ask one thing only.
Do not include a why field.
Keep questions short and clear.
"""


# ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# ///////////////////////////////////////////     FEATURE PLANNER    ///////////////////////////////////////////


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

Rules:
- Do not create circular dependencies.
- Every depends_on value must exactly match a feature name that appears earlier in the JSON.
- Keep the MVP focused on the clarified scope; do not add seller marketplace features unless admin/store management was requested.
"""


# ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# ///////////////////////////////////////////    SCREEN PLANNER    ///////////////////////////////////////////

SCREEN_PLANNER = """
You are a Screen Planning agent for a Flutter app.

App context:
{intent_json}

Features:
{features_json}

For every feature, generate the Flutter screens needed.
Also include: onboarding flow, splash screen, error screens.
Think like a Flutter developer â€” name screens with "Screen" suffix.
Use Riverpod-style names in state_needed by default, e.g. AuthProvider,
ProductProvider, CartProvider. Do not use Bloc names unless the app context
explicitly asks for bloc.
Set api_calls to Firebase SDK actions such as "Firestore: read meals" or
"Firebase Auth: sign in". Do not use REST paths like /api/v1.

IMPORTANT RULES:
- Every screen must have a unique name â€” never duplicate screen names.
- Every screen must have a non-empty route path (e.g. /home, /product/:id).
- Include an ErrorScreen with route /error.
- Include a SplashScreen with route /splash.
- If auth is needed, include a LoginScreen with route /login and SignupScreen with route /signup.
- If the app has admin features, admin screens must have distinct names prefixed with "Admin".

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
      "state_needed": ["<ProviderName>", ...],
      "api_calls":   ["<Firebase SDK action>", ...],
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

# ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# ///////////////////////////////////////////    NAVIGATION PLANNER    ///////////////////////////////////////////
NAVIGATION_PLANNER = """
You are a Navigation Planning agent for Flutter (using go_router).

App context:
{intent_json}

Screens list (ONLY use routes and screen names from this list):
{screens_json}

Design the complete navigation structure.

CRITICAL RULES:
- Every route in "routes" must match exactly a "route" field from the screens list above.
- Every route in "bottom_tabs" must also exist in the "routes" array.
- Do not invent routes that are not in the screen list.
- protected_routes and guest_routes must only contain paths from the routes array.

Return ONLY valid JSON:
{{
  "nav_type":        "<bottom_navigation|drawer|tab|none>",
  "bottom_tabs": [
    {{
      "label": "<Tab label>",
      "icon":  "<material icon name>",
      "route": "<route path â€” must exist in routes array>"
    }}
  ],
  "routes": [
    {{
      "path":        "<exact route from screens list>",
      "screen":      "<exact screen name from screens list>",
      "protected":   true|false,
      "params":      ["<param name>", ...]
    }}
  ],
  "protected_routes":  ["<route>", ...],
  "guest_routes":      ["<route>", ...],
  "deep_link_scheme":  "<e.g. myapp://>",
  "nested_navigators": [],
  "navigation_package": "go_router",
  "notes": "<auth guard strategy>"
}}
"""

# ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# ///////////////////////////////////////////    BACKEND PLANNER    ///////////////////////////////////////////

BACKEND_PLANNER = """
You are a Backend Planning agent for a Flutter app.

App context:
{intent_json}

Features:
{features_json}

Screens:
{screens_json}

Design Firebase backend requirements.

CRITICAL RULES:
- Use Firebase only.
- backend_type must be "firebase".
- auth_provider must be "firebase_auth".
- Use Cloud Firestore for app data.
- Use Firebase Storage only when files/images are needed.
- Use FCM only when push notifications are needed.
- Do not use REST, GraphQL, custom APIs, JWT, OAuth2, Supabase, FastAPI, Node APIs, or /api/v1 paths.
- api_endpoints must be [] because Flutter talks to Firebase SDKs directly.
- Describe Firebase services in firebase_services.
- Describe Firestore rules in security_rules.
- If COD (cash on delivery) is the payment method, set needs_payment_gateway: false.

Return ONLY valid JSON:
{{
  "needs_backend":          true,
  "backend_type":           "firebase",
  "realtime":               true|false,
  "realtime_reason":        "<short reason, or empty string>",
  "auth_provider":          "firebase_auth",
  "auth_methods":           ["<email_password>", ...],
  "file_storage":           "<firebase_storage|none>",
  "push_notifications":     true|false,
  "push_provider":          "<fcm|none>",
  "caching":                true|false,
  "background_jobs":        true|false,
  "needs_payment_gateway":  true|false,
  "payment_method":         "<stripe|cod|none>",
  "firebase_services":      ["firebase_auth", "cloud_firestore"],
  "firestore_collections":  ["<collection name>", ...],
  "security_rules":         ["<short Firestore/Auth rule>", ...],
  "third_party_apis": [
    {{
      "name":    "<API name>",
      "purpose": "<short purpose>",
      "url":     "<docs url if known>"
    }}
  ],
  "api_endpoints": [],
  "environment_variables": ["FIREBASE_API_KEY", "FIREBASE_PROJECT_ID", "FIREBASE_APP_ID"]
}}
"""

# ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# ///////////////////////////////////////////    DATABASE PLANNER    ///////////////////////////////////////////

DATABASE_PLANNER = """
You are a Database Planning agent for a Flutter app.

App context:
{intent_json}

Features:
{features_json}

Backend config:
{backend_json}

Design the complete Firestore schema.

CRITICAL RULES:
- Use Firebase Cloud Firestore only.
- database_type must be "firestore".
- Treat "tables" as Firestore collections for compatibility.
- Include one collection for every major MVP data area.
- Include a users collection when auth is needed.
- Do not use PostgreSQL, MySQL, SQLite, Supabase, REST, JWT, or custom API assumptions.
- Do not add collections for post-MVP features unless required by MVP auth/profile data.

Return ONLY valid JSON:
{{
  "database_type": "firestore",
  "tables": [
    {{
      "name": "<collection name>",
      "purpose": "<what this collection stores>",
      "fields": [
        {{
          "name":     "<field name>",
          "type":     "<String|int|double|bool|Timestamp|DocumentReference|List|Map>",
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
  "local_cache_strategy": "<short Firebase offline persistence/cache note>"
}}
"""

# ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# ///////////////////////////////////////////    ARCHITECTURE PLANNER    ///////////////////////////////////////////

ARCHITECTURE_PLANNER = """
You are a Flutter Architecture Planning agent.

App context:
{intent_json}

Complexity and features:
{features_json}

Design the complete Flutter architecture.
Be specific â€” a junior Flutter developer should be able to follow this plan.

CRITICAL RULES:
- Use Firebase SDKs for backend access.
- Do not use Dio, HTTP, Chopper, custom REST APIs, JWT, or manual token storage.
- Include firebase_core, firebase_auth, and cloud_firestore dependencies.
- Include firebase_storage only if file uploads/images are needed.
- Include firebase_messaging only if push notifications are needed.
- Use Firestore offline persistence for cached data.
- State management must be consistent: if riverpod, use only Provider/Notifier naming,
  not Bloc/Cubit naming.
- Every screen that shows user-specific data needs at least one provider in state_needed.

Return ONLY valid JSON:
{{
  "state_management": "<riverpod|bloc|provider|getx|mobx>",
  "state_management_reason": "<why this choice>",
  "architecture_pattern": "<feature_first_clean_architecture|layered_clean_architecture|mvc|mvvm>",
  "cart_strategy": "<firestore|local>",
  "folder_structure": [
    {{
      "path":    "<e.g. lib/features/auth/>",
      "purpose": "<what goes here>"
    }}
  ],
  "navigation_package": "<go_router|auto_route>",
  "network_layer": "firebase_sdk",
  "local_database": "firestore_offline_cache",
  "offline_first": true|false,
  "modular": true|false,
  "flavors": ["dev", "staging", "prod"],
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
    "recommended_packages": ["mockito", "flutter_test"]
  }},
  "security_rules": [
    "<e.g. Use Firebase Auth state and Firestore security rules>"
  ],
  "performance_notes": [
    "<e.g. Use ListView.builder for all lists, never ListView with children>"
  ],
  "accessibility_notes": [
    "<e.g. Wrap all tappable widgets with Semantics>"
  ]
}}
"""


# ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# ///////////////////////////////////////////    DESIGN SYSTEM PLANNER    ///////////////////////////////////////////

DESIGN_SYSTEM_PLANNER = """
You are a Flutter UI/UX Design System agent.

App context:
{intent_json}

App type: {app_type}
Target users: {target_users}

User's branding preferences (from clarifications â€” MUST be respected):
{branding_notes}

Design a complete Flutter design system.

CRITICAL RULES:
- If the user specified accent/primary color, use it exactly as primary_color.
- If the user specified background color (e.g. "wheat"), use the correct hex for it as background_color.
- Do NOT override user-specified colors with generic defaults.
- wheat = #F5DEB3, coral red = #FF4444, soft red accent = #E53935
- If user said "pastel" style, the theme must be "soft_pastel" and fonts must be playful/rounded.
- All colors must be valid 6-digit hex codes (e.g. #FF4444, not #F44).

Return ONLY valid JSON:
{{
  "theme":             "<modern_minimal|playful|professional|luxury|bold_editorial|soft_pastel|dark_techy>",
  "primary_color":     "<hex â€” user's accent color if specified>",
  "secondary_color":   "<hex>",
  "background_color":  "<hex â€” user's background color if specified>",
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

# ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# ///////////////////////////////////////////    VALIDATION PLANNER    ///////////////////////////////////////////

VALIDATION_AGENT = """
You are a Flutter App Plan Validator â€” the final quality gate.

Review this complete app plan and identify real structural issues only.

Full Plan:
{plan_json}

Check ONLY for these concrete issues:
1. Screen name appears more than once in the screens array â†’ critical
2. A route in bottom_tabs does not exist in the routes array â†’ critical
3. Auth provider is set but no LoginScreen exists in screens â†’ critical
4. needs_payment_gateway is true but no payments/transactions table exists â†’ warning
5. needs_payment_gateway is false (COD) â†’ do NOT flag missing payments table, this is correct
6. backend_type is not "firebase" or auth_provider is not "firebase_auth" â†’ critical
7. If backend_type is "firebase", api_endpoints must be []; do not require endpoint matches for Firebase SDK api_calls
8. primary_color and background_color are both close to the same hue (contrast issue) â†’ warning
9. A cart_items or cart table exists in database BUT architecture.cart_strategy is "local" â†’ warning
10. ErrorScreen is missing from screens â†’ suggestion

Do NOT flag:
- Missing post_mvp tables (these are intentionally excluded)
- Wishlist/reviews tables missing (post_mvp)
- Minor naming style differences
- Registration fields vs database fields â€” these can differ by design
- Firebase SDK api_calls without REST endpoints

Return ONLY valid JSON:
{{
  "validation_passed": true|false,
  "confidence_score":  <0.0 to 1.0>,
  "errors": [
    {{
      "severity": "<critical|warning|suggestion>",
      "category": "<screens|navigation|database|backend|architecture|design>",
      "issue":    "<specific, concrete issue â€” reference actual values from the plan>",
      "fix":      "<exact action to fix it>"
    }}
  ],
  "missing_info": ["<what the user never specified>"],
  "assumptions_made": ["<what the AI assumed>"],
  "ai_notes": ["<general improvement tips â€” keep to 3 max>"]
}}

validation_passed must be true if there are zero critical errors.
"""

# ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# ///////////////////////////////////////////    PLAN REPAIRER    ///////////////////////////////////////////

PLAN_REPAIRER = """
You are a Flutter app plan repair agent.

Fix the plan so it passes validation. Keep the same product idea and do not invent unrelated features.
Resolve every critical error and warning listed below using the smallest possible change.

Validation result:
{validation_json}

Current plan:
{plan_json}

REPAIR RULES:
1. For "auth_required: false but roles non-empty" â†’ patch that endpoint's roles to [].
2. For non-Firebase backend/auth â†’ set backend_type to "firebase", auth_provider to "firebase_auth", and api_endpoints to [].
3. For "cart_strategy mismatch" â†’ patch flutter_architecture.cart_strategy to match what backend has.
4. For "design color inconsistency" â†’ patch design_system.primary_color to the user's specified color.
5. For "missing ErrorScreen" â†’ append a minimal ErrorScreen to screens and /error to navigation.routes.
6. For "bottom_tab route not in routes" â†’ append the missing route to navigation.routes.
7. For "missing LoginScreen" â†’ append LoginScreen to screens and /login to navigation.routes.
8. Never remove existing screens or tables â€” only add or patch.

Return ONLY valid JSON with small patches:
{{
  "summary": "<one sentence describing the repairs made>",
  "patches": [
    {{
      "op":    "<set|append|remove>",
      "path":  "<JSON Pointer e.g. /backend/api_endpoints>",
      "value": <the corrected value>
    }}
  ]
}}

Use "append" to add items to arrays.
Use "set" to overwrite a specific field or index.
Return the minimum patches needed â€” do not return the full plan.
"""

PLAN_PATCHER = """
You are a JSON patch editor for a Flutter app master plan.

User request:
\"\"\"{instruction}\"\"\"

Relevant plan context only:
{plan_context}

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
- The context may include only relevant sections, but paths must target the full master plan.
"""
