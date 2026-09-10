from __future__ import annotations

from fastapi import APIRouter

from app.api.benchmarks_loader import load_all_benchmarks

router = APIRouter()


@router.get("/benchmarks")
def get_benchmarks() -> dict:
    records = load_all_benchmarks()
    by_category: dict[str, int] = {}
    for r in records:
        by_category[r["category"]] = by_category.get(r["category"], 0) + 1
    return {"total": len(records), "by_category": by_category, "benchmarks": records}
