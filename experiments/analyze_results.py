#!/usr/bin/env python3
"""Compares multiple experiment result JSON files (e.g. different models).

Usage:
    python experiments/analyze_results.py experiments/results/*.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result_files", nargs="+", type=Path)
    args = parser.parse_args()

    print(f"{'file':50s} {'model':20s} {'accept%':>8s} {'reject%':>8s} {'avg_lat_ms':>11s} {'avg_reduc%':>11s}")
    for path in args.result_files:
        data = json.loads(path.read_text())
        summary = data["summary"]
        model = data["rows"][0]["model"] if data["rows"] else "n/a"
        print(
            f"{path.name:50s} {model:20s} "
            f"{summary['acceptance_rate_pct']:>8.2f} {summary['rejection_rate_pct']:>8.2f} "
            f"{summary['avg_verification_latency_ms']:>11.3f} {summary['avg_instruction_reduction_pct']:>11.2f}"
        )


if __name__ == "__main__":
    main()
