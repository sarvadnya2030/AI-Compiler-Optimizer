from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.optimizer.llm_optimizer import build_generator
from app.optimizer.pipeline import PipelineError, run_optimization
from app.verifier.equivalence import EquivalenceChecker

router = APIRouter()


class OptimizeRequest(BaseModel):
    program: str = Field(..., description="Source code in the small IR language")
    num_candidates: int = Field(default=5, ge=1, le=20)
    llm_backend: str | None = Field(default=None, description="'mock' or 'ollama'; defaults to server config")
    ollama_model: str | None = None


@router.post("/optimize")
def optimize(req: OptimizeRequest) -> dict:
    backend = req.llm_backend or settings.llm_backend
    try:
        generator = build_generator(
            backend,
            ollama_base_url=settings.ollama_base_url,
            ollama_model=req.ollama_model or settings.ollama_model,
            ollama_timeout_s=settings.ollama_timeout_s,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    checker = EquivalenceChecker(timeout_ms=settings.z3_timeout_ms)

    try:
        report = run_optimization(req.program, generator, req.num_candidates, checker=checker)
    except PipelineError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return report.to_dict()
