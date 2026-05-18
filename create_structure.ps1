# Root folder
$root = "planning_engine"

# Create directories
$dirs = @(
    "$root/core",
    "$root/agents",
    "$root/validation",
    "$root/orchestration",
    "$root/outputs"
)

foreach ($dir in $dirs) {
    New-Item -ItemType Directory -Path $dir -Force
}

# Create files
$files = @(
    "$root/core/gemini_client.py",
    "$root/core/prompt_templates.py",
    "$root/core/schema.py",

    "$root/agents/intent_analyzer.py",
    "$root/agents/requirement_extractor.py",
    "$root/agents/feature_planner.py",
    "$root/agents/screen_planner.py",
    "$root/agents/navigation_planner.py",
    "$root/agents/backend_planner.py",
    "$root/agents/database_planner.py",
    "$root/agents/architecture_planner.py",

    "$root/validation/validator.py",

    "$root/orchestration/planning_orchestrator.py",

    "$root/outputs/sample_plan.json",

    "$root/config.py"
)

foreach ($file in $files) {
    New-Item -ItemType File -Path $file -Force
}

Write-Host "Project structure created successfully!"