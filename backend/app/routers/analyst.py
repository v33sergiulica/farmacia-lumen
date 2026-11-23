"""Headless AI Analyst router stub (implemented in Phase 5)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..schemas import AnalystQuestionRequest

router = APIRouter(tags=["analyst"])


@router.post("/analyst/ask")
def ask_analyst(_payload: AnalystQuestionRequest) -> dict[str, str]:
    raise HTTPException(
        status_code=501,
        detail="Headless AI Analyst endpoint will be implemented in Phase 5.",
    )
