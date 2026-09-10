#!/usr/bin/env python3
"""Runs the optimizer+verifier pipeline over the benchmark suite and
records per-candidate results to JSON and CSV, plus aggregate research
metrics (acceptance rate, verification latency, instruction reduction).

Usage:
    python experiments/run_experiment.py
    python experiments/run_experiment.py --backend mock --num-candidates 3
    python experiments/run_experiment.py --backend ollama --model qwen3:0.6b
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.api.benchmarks_loader import load_all_benchmarks  # noqa: E402
from app.optimizer.llm_optimizer import build_generator  # noqa: E402
from app.optimizer.pipeline import PipelineError, run_optimization  # noqa: E402
from app.verifier.equivalence import EquivalenceChecker, VerificationStatus  # noqa: E402

RESULTS_DIR = REPO_ROOT / "experiments" / "results"

FIELDNAMES = [
    "benchmark_id",
    "category",
    "model",
    "candidate_id",
    "verification_status",
    "verification_time_ms",
    "original_instruction_count",
    "optimized_instruction_count",
    "instruction_reduction_pct",
    "counterexample_found",
]


def run(
    backend: str, num_candidates: int, ollama_base_url: str, ollama_model: str, ollama_timeout_s: float = 120.0
) -> list[dict]:
    generator = build_generator(
        backend, ollama_base_url=ollama_base_url, ollama_model=ollama_model, ollama_timeout_s=ollama_timeout_s
    )
    checker = EquivalenceChecker()
    records = load_all_benchmarks()

    rows: list[dict] = []
    for benchmark in records:
        try:
            report = run_optimization(benchmark["program"], generator, num_candidates, checker=checker)
        except PipelineError as e:
            print(f"[skip] {benchmark['id']}: {e}", file=sys.stderr)
            continue

        for candidate in report.candidates:
            if candidate.decision is None:
                rows.append(
                    {
                        "benchmark_id": benchmark["id"],
                        "category": benchmark["category"],
                        "model": generator.name,
                        "candidate_id": candidate.index,
                        "verification_status": "PARSE_ERROR",
                        "verification_time_ms": 0.0,
                        "original_instruction_count": len(report.original_ir.instructions),
                        "optimized_instruction_count": None,
                        "instruction_reduction_pct": None,
                        "counterexample_found": False,
                    }
                )
                continue

            verification = candidate.decision.verification
            metrics = candidate.decision.metrics
            rows.append(
                {
                    "benchmark_id": benchmark["id"],
                    "category": benchmark["category"],
                    "model": generator.name,
                    "candidate_id": candidate.index,
                    "verification_status": verification.status.value,
                    "verification_time_ms": verification.verification_time_ms,
                    "original_instruction_count": metrics.original.instruction_count if metrics else None,
                    "optimized_instruction_count": metrics.optimized.instruction_count if metrics else None,
                    "instruction_reduction_pct": metrics.instruction_reduction_pct if metrics else None,
                    "counterexample_found": verification.counterexample is not None,
                }
            )

    return rows


def summarize(rows: list[dict]) -> dict:
    total = len(rows)
    accepted = sum(1 for r in rows if r["verification_status"] == VerificationStatus.EQUIVALENT.value)
    rejected = total - accepted
    latencies = [r["verification_time_ms"] for r in rows if r["verification_time_ms"] is not None]
    reductions = [r["instruction_reduction_pct"] for r in rows if r["instruction_reduction_pct"] is not None]

    return {
        "total_candidates": total,
        "accepted": accepted,
        "rejected": rejected,
        "acceptance_rate_pct": round(accepted / total * 100, 2) if total else 0.0,
        "rejection_rate_pct": round(rejected / total * 100, 2) if total else 0.0,
        "avg_verification_latency_ms": round(sum(latencies) / len(latencies), 3) if latencies else 0.0,
        "avg_instruction_reduction_pct": round(sum(reductions) / len(reductions), 2) if reductions else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", default="mock", choices=["mock", "ollama"])
    parser.add_argument("--num-candidates", type=int, default=3)
    parser.add_argument("--ollama-base-url", default="http://localhost:11434")
    parser.add_argument("--model", default="qwen3:0.6b", help="Ollama model name (ignored for mock)")
    args = parser.parse_args()

    rows = run(args.backend, args.num_candidates, args.ollama_base_url, args.model)
    summary = summarize(rows)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    model_tag = args.model if args.backend == "ollama" else "mock"
    base_name = f"{timestamp}_{args.backend}_{model_tag}"

    json_path = RESULTS_DIR / f"{base_name}.json"
    csv_path = RESULTS_DIR / f"{base_name}.csv"

    json_path.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2))

    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(json.dumps(summary, indent=2))
    print(f"\nWrote {json_path}")
    print(f"Wrote {csv_path}")


if __name__ == "__main__":
    main()
