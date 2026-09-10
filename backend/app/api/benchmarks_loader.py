"""Loads benchmark programs from the repo-level benchmarks/ directory.

Shared by the /api/benchmarks and /api/experiments routes and by
experiments/run_experiment.py, so there is exactly one notion of what a
benchmark record looks like.
"""
from __future__ import annotations

import json
from pathlib import Path

# backend/app/api/benchmarks_loader.py -> repo_root/benchmarks
REPO_ROOT = Path(__file__).resolve().parents[3]
BENCHMARKS_DIR = REPO_ROOT / "benchmarks"


def list_benchmark_files() -> list[Path]:
    if not BENCHMARKS_DIR.exists():
        return []
    return sorted(BENCHMARKS_DIR.glob("*.jsonl"))


def load_all_benchmarks() -> list[dict]:
    records: list[dict] = []
    for path in list_benchmark_files():
        category = path.stem
        with path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as e:
                    raise ValueError(f"{path}:{line_no}: invalid JSON: {e}") from e
                record.setdefault("category", category)
                records.append(record)
    return records
