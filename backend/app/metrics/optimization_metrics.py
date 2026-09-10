"""IR-level optimization metrics.

These are purely structural (instruction counts). They are NOT a proxy
for real CPU speedup -- no native code is generated or benchmarked in
this MVP. Always label results as "IR-level metrics" in any UI/report.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.compiler import ir as IR

_ARITH_OPS = set(IR.ARITH_OPS)


@dataclass
class IRMetrics:
    instruction_count: int
    arithmetic_instruction_count: int

    def to_dict(self) -> dict:
        return {
            "instruction_count": self.instruction_count,
            "arithmetic_instruction_count": self.arithmetic_instruction_count,
        }


@dataclass
class OptimizationMetrics:
    original: IRMetrics
    optimized: IRMetrics
    instruction_reduction_pct: float

    def to_dict(self) -> dict:
        return {
            "original": self.original.to_dict(),
            "optimized": self.optimized.to_dict(),
            "instruction_reduction_pct": self.instruction_reduction_pct,
        }


def compute_ir_metrics(fn: IR.IRFunction) -> IRMetrics:
    instruction_count = len(fn.instructions)
    arithmetic_count = sum(1 for i in fn.instructions if isinstance(i, IR.BinArithInstr))
    return IRMetrics(instruction_count=instruction_count, arithmetic_instruction_count=arithmetic_count)


def compute_optimization_metrics(original: IR.IRFunction, optimized: IR.IRFunction) -> OptimizationMetrics:
    original_metrics = compute_ir_metrics(original)
    optimized_metrics = compute_ir_metrics(optimized)

    if original_metrics.instruction_count == 0:
        reduction_pct = 0.0
    else:
        reduction_pct = round(
            (original_metrics.instruction_count - optimized_metrics.instruction_count)
            / original_metrics.instruction_count
            * 100,
            2,
        )

    return OptimizationMetrics(
        original=original_metrics,
        optimized=optimized_metrics,
        instruction_reduction_pct=reduction_pct,
    )
