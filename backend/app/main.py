"""FastAPI application entrypoint.

Run with:
    uvicorn app.main:app --reload --app-dir backend
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import benchmarks, experiments, optimize, verify
from app.config import settings

logging.basicConfig(level=settings.log_level)

app = FastAPI(
    title="AI Compiler Optimizer",
    description="LLM-Generated Optimizations with Formal Equivalence Verification",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(optimize.router, prefix="/api", tags=["optimize"])
app.include_router(verify.router, prefix="/api", tags=["verify"])
app.include_router(benchmarks.router, prefix="/api", tags=["benchmarks"])
app.include_router(experiments.router, prefix="/api", tags=["experiments"])


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "llm_backend": settings.llm_backend,
        "mock_llm": settings.mock_llm,
    }
