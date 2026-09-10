from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.optimizer.pipeline import PipelineError, verify_pair
from app.verifier.equivalence import EquivalenceChecker

router = APIRouter()


class VerifyRequest(BaseModel):
    original_program: str = Field(..., description="Source of the original program")
    optimized_program: str = Field(..., description="Source of the candidate optimized program")


@router.post("/verify")
def verify(req: VerifyRequest) -> dict:
    checker = EquivalenceChecker(timeout_ms=settings.z3_timeout_ms)
    try:
        return verify_pair(req.original_program, req.optimized_program, checker=checker)
    except PipelineError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
