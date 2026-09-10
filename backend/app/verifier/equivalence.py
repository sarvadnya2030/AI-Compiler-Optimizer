"""Formal equivalence checking between two IR functions via Z3.

The central query, for two functions over the same free variables:

    exists an input such that original_output != optimized_output ?

    UNSAT -> no such input exists  -> EQUIVALENT
    SAT   -> such an input exists  -> NOT_EQUIVALENT (counterexample extracted)
    UNKNOWN (solver gave up, e.g. timeout) -> UNKNOWN (never treated as equivalent)
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum

import z3

from app.compiler import ir as IR
from app.verifier.counterexample import Counterexample
from app.verifier.z3_encoder import EncodedFunction, EncodingError, Z3Encoder


class VerificationStatus(str, Enum):
    EQUIVALENT = "EQUIVALENT"
    NOT_EQUIVALENT = "NOT_EQUIVALENT"
    UNKNOWN = "UNKNOWN"
    SIGNATURE_MISMATCH = "SIGNATURE_MISMATCH"
    ENCODING_ERROR = "ENCODING_ERROR"


@dataclass
class VerificationResult:
    status: VerificationStatus
    z3_result: str  # "unsat" | "sat" | "unknown" | "n/a"
    counterexample: Counterexample | None
    verification_time_ms: float
    error_message: str | None = None

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "z3_result": self.z3_result,
            "counterexample": self.counterexample.to_dict() if self.counterexample else None,
            "verification_time_ms": self.verification_time_ms,
            "error_message": self.error_message,
        }


DEFAULT_TIMEOUT_MS = 5000


class EquivalenceChecker:
    def __init__(self, timeout_ms: int = DEFAULT_TIMEOUT_MS):
        self.timeout_ms = timeout_ms
        self._encoder = Z3Encoder()

    def verify(self, original_ir: IR.IRFunction, optimized_ir: IR.IRFunction) -> VerificationResult:
        start = time.perf_counter()

        if set(original_ir.params) != set(optimized_ir.params):
            elapsed = _elapsed_ms(start)
            return VerificationResult(
                status=VerificationStatus.SIGNATURE_MISMATCH,
                z3_result="n/a",
                counterexample=None,
                verification_time_ms=elapsed,
                error_message=(
                    f"parameter sets differ: original={sorted(original_ir.params)} "
                    f"optimized={sorted(optimized_ir.params)}"
                ),
            )

        try:
            original_enc = self._encoder.encode(original_ir)
            optimized_enc = self._encoder.encode(optimized_ir)
        except EncodingError as e:
            elapsed = _elapsed_ms(start)
            return VerificationResult(
                status=VerificationStatus.ENCODING_ERROR,
                z3_result="n/a",
                counterexample=None,
                verification_time_ms=elapsed,
                error_message=str(e),
            )

        solver = z3.Solver()
        solver.set("timeout", self.timeout_ms)
        # Both encodings use z3.Int(name) for shared parameter names, so
        # they automatically refer to the same free symbolic variables.
        solver.add(original_enc.return_expr != optimized_enc.return_expr)

        z3_status = solver.check()
        elapsed = _elapsed_ms(start)

        if z3_status == z3.unsat:
            return VerificationResult(
                status=VerificationStatus.EQUIVALENT,
                z3_result="unsat",
                counterexample=None,
                verification_time_ms=elapsed,
            )

        if z3_status == z3.sat:
            model = solver.model()
            counterexample = self._build_counterexample(model, original_enc, optimized_enc)
            return VerificationResult(
                status=VerificationStatus.NOT_EQUIVALENT,
                z3_result="sat",
                counterexample=counterexample,
                verification_time_ms=elapsed,
            )

        # z3.unknown -- solver could not decide (e.g. timeout). Never
        # treated as equivalent.
        return VerificationResult(
            status=VerificationStatus.UNKNOWN,
            z3_result="unknown",
            counterexample=None,
            verification_time_ms=elapsed,
            error_message=solver.reason_unknown() if hasattr(solver, "reason_unknown") else None,
        )

    @staticmethod
    def _build_counterexample(
        model: "z3.ModelRef", original_enc: EncodedFunction, optimized_enc: EncodedFunction
    ) -> Counterexample:
        inputs: dict[str, int] = {}
        for name, var in original_enc.params.items():
            value = model.eval(var, model_completion=True)
            inputs[name] = value.as_long()

        original_val = model.eval(original_enc.return_expr, model_completion=True).as_long()
        optimized_val = model.eval(optimized_enc.return_expr, model_completion=True).as_long()

        return Counterexample(
            inputs=inputs,
            original_output=original_val,
            optimized_output=optimized_val,
        )


def _elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 3)
