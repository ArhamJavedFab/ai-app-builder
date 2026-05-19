from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

ENGINE_DIR = Path(__file__).resolve().parents[1]
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))

import config
from agents.intent_analyzer import analyze_intent
from agents.requirement_extractor import (
    build_required_startup_questions,
    build_startup_answers,
)
from cast_calculation.usage_tracker import (
    finish_usage_run,
    format_cost_summary,
    start_usage_run,
)
from core.summary import save_summary
from orchestration.planning_orchestrator import run_planning_pipeline
from view.plan_highlights import build_plain_language_highlights


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=8000)
    intent: dict[str, Any] | None = None
    questions: list[dict[str, Any]] = Field(default_factory=list)
    answers: dict[str, str] = Field(default_factory=dict)


class StartRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=8000)


class StartResponse(BaseModel):
    prompt: str
    intent: dict[str, Any]
    questions: list[dict[str, Any]]


class GenerateResponse(BaseModel):
    plan: dict[str, Any]
    highlights: list[str]
    cost_summary: str
    plan_path: str
    summary_path: str


app = FastAPI(title="Planning Engine Web", version="1.0.0")
templates = Jinja2Templates(directory=str(Path(__file__).with_name("templates")))


def _summary_path_for(output_path: str) -> str:
    base, _ext = os.path.splitext(output_path)
    return f"{base}{config.SUMMARY_FILENAME_SUFFIX}"


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    return Response(status_code=204)


# FASTAPI WEB CHAT FLOW:
# Step 1 asks Gemini for prompt-specific clarification questions and returns
# them to the browser. Nothing calls terminal input() in this route.
@app.post("/api/start", response_model=StartResponse)
async def start_plan(payload: StartRequest) -> StartResponse:
    if config.GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE":
        raise HTTPException(
            status_code=400,
            detail="GEMINI_API_KEY is not set in planning_engine/.env.",
        )

    run_id = start_usage_run("web_question_generation", {"source": "fastapi_view"})
    try:
        config.VERBOSE = False
        prompt = payload.prompt.strip()
        intent = analyze_intent(prompt)
        questions = build_required_startup_questions(prompt, intent)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        finish_usage_run(run_id)

    return StartResponse(prompt=prompt, intent=intent, questions=questions)


# FASTAPI WEB CHAT FLOW:
# Step 2 receives answers collected by the browser and runs the same pipeline
# with startup_clarifications, so the CLI input() question function is skipped.
@app.post("/api/generate", response_model=GenerateResponse)
async def generate_plan(payload: GenerateRequest) -> GenerateResponse:
    if config.GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE":
        raise HTTPException(
            status_code=400,
            detail="GEMINI_API_KEY is not set in planning_engine/.env.",
        )

    run_id = start_usage_run("web_planning_pipeline", {"source": "fastapi_view"})
    try:
        config.VERBOSE = False
        clarifications = build_startup_answers(payload.questions, payload.answers)
        master_plan = run_planning_pipeline(
            payload.prompt.strip(),
            startup_clarifications=clarifications,
        )
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)
        output_path = os.path.join(config.OUTPUT_DIR, config.FINAL_PLAN_FILENAME)
        master_plan.save(output_path)

        plan = master_plan.to_dict()
        summary_path = _summary_path_for(output_path)
        save_summary(plan, summary_path)
        highlights = build_plain_language_highlights(plan)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        usage_result = finish_usage_run(run_id)

    return GenerateResponse(
        plan=plan,
        highlights=highlights,
        cost_summary=format_cost_summary(usage_result),
        plan_path=output_path,
        summary_path=summary_path,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("view.app:app", host="127.0.0.1", port=8000, reload=True)
