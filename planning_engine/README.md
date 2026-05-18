# 🚀 Flutter App Planning Engine

> Convert a raw app idea into a production-ready Flutter Master Plan JSON in seconds.

Powered by **Google Gemini AI** — multi-agent pipeline with intent analysis, requirement clarification, screen/navigation/backend/database/architecture planning, design system generation, and automated validation.

---

## 📁 Project Structure

```
planning_engine/
│
├── core/
│   ├── gemini_client.py       # Gemini API wrapper (fast + pro models)
│   ├── prompt_templates.py    # All agent prompts (one file, easy to tune)
│   └── schema.py              # MasterPlan dataclass — the output contract
│
├── agents/
│   ├── intent_analyzer.py     # Stage 1: What is the user building?
│   ├── requirement_extractor.py # Stage 2: Ask clarifying questions interactively
│   ├── feature_planner.py     # Stage 3: Feature modules + MVP vs post-MVP
│   ├── screen_planner.py      # Stage 4: Flutter screens + reusable widgets
│   ├── navigation_planner.py  # Stage 5: go_router routes, bottom tabs, guards
│   ├── backend_planner.py     # Stage 6: REST/Firebase, auth, APIs, storage
│   ├── database_planner.py    # Stage 7: Tables, fields, relations, indexes
│   └── architecture_planner.py # Stage 8: State mgmt, folder structure, deps, design
│
├── validation/
│   └── validator.py           # Rule-based + LLM validation (Pro model)
│
├── orchestration/
│   └── planning_orchestrator.py # Runs all agents in sequence
│
├── outputs/
│   └── sample_plan.json       # Full example output for a food delivery app
│
├── main.py                    # CLI entry point
├── config.py                  # All tunable parameters
└── requirements.txt
```

---

## ⚙️ Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set your Gemini API key

Create `planning_engine/.env`:

```env
GEMINI_API_KEY=your_key_here
GEMINI_MODEL_FAST=gemini-2.5-flash
GEMINI_MODEL_PRO=gemini-2.5-pro
GEMINI_MAX_TOKENS=16384
GEMINI_JSON_RETRIES=1
```

Or set it only for the current PowerShell session:

```powershell
$env:GEMINI_API_KEY='your_key_here'
```

Get a free key at: https://aistudio.google.com/app/apikey

---

## 🏃 Running the Engine

### Interactive mode (recommended)

```bash
python main.py
```

The CLI will prompt you to describe your app. Press Enter twice when done.

### Inline prompt

```bash
python main.py --prompt "Build a food delivery app with login, cart, payment, and order tracking"
```

### Custom output file

```bash
python main.py --prompt "Build a task manager app" --output my_app_plan.json
```

### Quiet mode (suppress step logs)

```bash
python main.py --prompt "..." --quiet
```

---

## 🔄 Pipeline Stages

```
User Prompt
    │
    ▼
[Stage 1] Intent Analyzer          — Gemini Flash
    │  domain, complexity, modules, confidence score
    │
    ▼
[Stage 2] Requirement Extractor    — Gemini Flash
    │  interactive Q&A if confidence < 65%
    │
    ▼
[Stage 3] Feature Planner          — Gemini Flash
    │  feature modules, MVP vs post-MVP
    │
    ▼
[Stage 4] Screen Planner           — Gemini Flash
    │  Flutter screens, widgets, dialogs, bottom sheets
    │
    ▼
[Stage 5] Navigation Planner       — Gemini Flash
    │  go_router routes, bottom tabs, guards, deep links
    │
    ▼
[Stage 6] Backend Planner          — Gemini Flash
    │  REST/Firebase/Supabase, auth, APIs, env vars
    │
    ▼
[Stage 7] Database Planner         — Gemini Flash
    │  tables, fields, relations, indexes, local cache strategy
    │
    ▼
[Stage 8a] Architecture Planner    — Gemini Pro  ← reasoning model
    │  Riverpod/Bloc, folder structure, all dependencies
    │
[Stage 8b] Design System Planner   — Gemini Flash
    │  colors, fonts, spacing, dark mode, animation style
    │
    ▼
[Stage 9] Validator                — Gemini Pro  ← reasoning model
    │  rule-based checks + LLM audit
    │
    ▼
Master Plan JSON  →  outputs/master_plan.json
```

---

## 📄 Output: Master Plan JSON

The output is optimized for Flutter code generation. Key sections:

| Section | What Design/Build agents consume |
|---|---|
| `screens[]` | Screen names, routes, widgets, state providers, API calls |
| `navigation` | go_router setup, bottom tabs, protected routes |
| `flutter_architecture` | State management, folder structure, packages |
| `design_system` | Colors, fonts, spacing — directly maps to ThemeData |
| `flutter_dependencies` | pubspec.yaml dependencies (with versions) |
| `database_tables` | Isar/Hive local models or backend schema |
| `backend.api_endpoints` | API service layer generation |
| `testing_strategy` | Test file scaffolding |

See `outputs/sample_plan.json` for a complete example (food delivery app).

---

## 🎛️ Configuration (`config.py`)

| Setting | Default | Description |
|---|---|---|
| `GEMINI_MODEL_FAST` | `gemini-2.0-flash` | Used for most agents (speed) |
| `GEMINI_MODEL_PRO` | `gemini-2.5-pro-preview-05-06` | Architecture + Validation |
| `GEMINI_TEMPERATURE` | `0.3` | Low = more deterministic JSON |
| `MIN_INTENT_CONFIDENCE` | `0.65` | Below this → ask clarifying questions |
| `MAX_CLARIFICATION_QUESTIONS` | `5` | Max questions to ask user |
| `VERBOSE` | `True` | Show step-by-step progress |

---

## 💡 Tips for Best Results

**Good prompt:**
> "Build a marketplace app where freelancers can list services, clients can browse and book them, with chat, payments via Stripe, and an admin panel for moderation."

**Too vague (will trigger clarification):**
> "Build an app"

The engine will ask follow-up questions when your prompt is ambiguous — just answer them in the terminal.

---

## 🗺️ What's Next (Design & Build Phase)

The `master_plan.json` output is designed to feed directly into:

- **Design Agent** → generates Flutter screen layouts, widget trees, ThemeData
- **Build Agent** → generates actual `.dart` files using feature-first clean architecture
- **Backend Agent** → generates FastAPI/Node routes from `api_endpoints`
- **Database Agent** → generates Isar schemas or SQL migrations from `database_tables`
