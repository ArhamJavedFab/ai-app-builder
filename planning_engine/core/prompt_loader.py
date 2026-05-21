# ============================================================
# core/prompt_loader.py
# ============================================================

from pathlib import Path
import re

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def load_prompt_template(filename: str) -> str:
    """Load the ## Prompt Template section from a markdown prompt file."""
    path = PROMPTS_DIR / filename
    content = path.read_text(encoding="utf-8")
    match = re.search(r"## Prompt Template\n(.*?)(?=\n## |\Z)", content, re.DOTALL)
    if not match:
        raise ValueError(f"Prompt Template section not found in {path}")
    return match.group(1).strip()
