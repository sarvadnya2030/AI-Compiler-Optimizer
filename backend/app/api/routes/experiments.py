"""POST /api/experiments -- run the optimizer+verifier over the benchmark
suite (or a subset) synchronously and return aggregate research metrics.
For larger/offline runs, prefer experiments/run_experiment.py directly.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.benchmarks_loader import load_all_benchmarks
from app.config import settings
from app.optimizer.llm_optimizer import build_generator
from app.optimizer.pipeline import PipelineError, run_optimization
from app.verifier.equivalence import EquivalenceChecker

router = APIRouter()


class ExperimentRequest(BaseModel):
    llm_backend: str | None = None
    num_candidates: int = Field(default=3, ge=1, le=10)
    category: str | None = Field(default=None, description="Restrict to one benchmark category")
    limit: int | None = Field(default=None, ge=1)


@router.post("/experiments")
def run_experiments(req: ExperimentRequest) -> dict:
    backend = req.llm_backend or settings.llm_backend
    generator = build_generator(
        backend,
        ollama_base_url=settings.ollama_base_url,
        ollama_model=settings.ollama_model,
        ollama_timeout_s=settings.ollama_timeout_s,
    )
    checker = EquivalenceChecker(timeout_ms=settings.z3_timeout_ms)

    records = load_all_benchmarks()
    if req.category:
        records = [r for r in records if r["category"] == req.category]
    if req.limit:
        records = records[: req.limit]

    results = []
    for record in records:
        try:
            report = run_optimization(record["program"], generator, req.num_candidates, checker=checker)
            results.append({"benchmark_id": record["id"], "category": record["category"], **report.to_dict()})
        except PipelineError as e:
            results.append({"benchmark_id": record["id"], "category": record["category"], "error": str(e)})

    return {"generator": generator.name, "benchmark_count": len(records), "results": results}
