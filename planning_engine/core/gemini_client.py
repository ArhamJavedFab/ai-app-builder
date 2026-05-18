# ============================================================
# core/gemini_client.py — Gemini API wrapper (google-genai SDK)
# ============================================================

import json
import re
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config
from cast_calculation.usage_tracker import log_llm_call

try:
    from google import genai
    from google.genai import errors as genai_errors
    from google.genai import types as genai_types
except ImportError:
    raise ImportError(
        "google-genai is not installed.\n"
        "Run:  pip install google-genai"
    )


# ── Initialise client once ───────────────────────────────────
_client = genai.Client(api_key=config.GEMINI_API_KEY)


def call_gemini(prompt: str, use_pro: bool = False) -> str:
    """
    Raw text call to Gemini.
    Returns the raw string response.
    """
    model_name = config.GEMINI_MODEL_PRO if use_pro else config.GEMINI_MODEL_FAST

    try:
        response = _client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                temperature=config.GEMINI_TEMPERATURE,
                max_output_tokens=config.GEMINI_MAX_TOKENS,
                response_mime_type="application/json",
            ),
        )
    except genai_errors.APIError as e:
        log_llm_call(
            model=model_name,
            prompt=prompt,
            success=False,
            error=str(e),
        )
        raise RuntimeError(
            "Gemini API request failed.\n"
            f"Model: {model_name}\n"
            f"Error: {e}\n\n"
            "If this is a model access error, set GEMINI_MODEL_FAST and "
            "GEMINI_MODEL_PRO in planning_engine/.env."
        ) from e

    output = (response.text or "").strip()
    log_llm_call(
        model=model_name,
        prompt=prompt,
        output=output,
        response=response,
        success=True,
    )
    return output


def call_gemini_json(prompt: str, use_pro: bool = False) -> dict | list:
    """
    Call Gemini and parse the response as JSON.
    Strips markdown fences if present.
    Raises RuntimeError on parse failure.
    """
    raw = ""
    json_error = None

    for attempt in range(config.GEMINI_JSON_RETRIES + 1):
        retry_note = ""
        if attempt:
            retry_note = (
                "\n\nYour previous response was not valid JSON. Return only "
                "complete, parseable JSON with no markdown fences or commentary."
            )

        raw = call_gemini(prompt + retry_note, use_pro=use_pro)

        # Strip ```json ... ``` fences
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned.strip())

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            json_error = e

    preview = raw.strip().replace("\n", " ")
    if len(preview) > 600:
        preview = f"{preview[:600]}..."

    raise RuntimeError(
        "Gemini returned invalid JSON, so the pipeline cannot safely "
        "continue.\n"
        f"JSON error: {json_error}\n"
        f"Model output preview: {preview}\n\n"
        "Try running again. If this repeats, increase GEMINI_MAX_TOKENS "
        "or use a stronger model in planning_engine/.env."
    ) from json_error
