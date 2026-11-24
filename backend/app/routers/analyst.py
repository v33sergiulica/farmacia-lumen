"""Headless AI Analyst router (POST /api/v1/analyst/ask)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..schemas import AnalystQuestionRequest, AnalystResponse
from ..services.analyst import (
    AnalystConfigError,
    AnalystExecutionError,
    SqlSecurityError,
    answer_question,
)

router = APIRouter(tags=["analyst"])


@router.post("/analyst/ask", response_model=AnalystResponse)
def ask_analyst(payload: AnalystQuestionRequest) -> AnalystResponse:
    try:
        return answer_question(payload.question, payload.filters)
    except AnalystConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except SqlSecurityError as exc:
        raise HTTPException(status_code=400, detail=f"Blocked unsafe SQL: {exc}") from exc
    except AnalystExecutionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
