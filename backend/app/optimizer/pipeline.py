"""Ties the whole pipeline together: source -> IR -> candidates -> verify -> decide.

    Source Program -> Parser/Frontend -> IR -> LLM Optimizer -> Candidate Parser
        -> Z3 Semantic Encoder -> Equivalence Check -> ACCEPT/REJECT -> Metrics
"""
from __future__ import annotations

from dataclasses import dataclass

from app.compiler import ir as IR
from app.compiler.lowering import LoweringError, lower_function
from app.compiler.parser import ParseError, parse_function
from app.optimizer.candidate_parser import parse_candidate
from app.optimizer.decision import OptimizationDecision, decide
from app.optimizer.llm_optimizer import OptimizationGenerator
from app.metrics.optimization_metrics import compute_optimization_metrics
from app.verifier.equivalence import EquivalenceChecker, VerificationResult, VerificationStatus


@dataclass
class CandidateReport:
    index: int
    raw_text: str
    parse_error: str | None
    candidate_ir: IR.IRFunction | None
    decision: OptimizationDecision | None

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "raw_candidate_text": self.raw_text,
            "parse_error": self.parse_error,
            "candidate_ir": IR.to_dict(self.candidate_ir) if self.candidate_ir else None,
            "accepted": self.decision.accepted if self.decision else False,
            "verification": self.decision.verification.to_dict() if self.decision else None,
            "metrics": self.decision.metrics.to_dict() if (self.decision and self.decision.metrics) else None,
        }


@dataclass
class OptimizationRunReport:
    original_ir: IR.IRFunction
    candidates: list[CandidateReport]
    generator_name: str

    def to_dict(self) -> dict:
        return {
            "original_ir": IR.to_dict(self.original_ir),
            "generator": self.generator_name,
            "candidates": [c.to_dict() for c in self.candidates],
            "summary": _summarize(self.candidates),
        }


class PipelineError(Exception):
    pass


def compile_source(source: str) -> IR.IRFunction:
    try:
        fn = parse_function(source)
    except ParseError as e:
        raise PipelineError(f"parse error: {e}") from e
    try:
        return lower_function(fn)
    except LoweringError as e:
        raise PipelineError(f"lowering error: {e}") from e


def run_optimization(
    source: str,
    generator: OptimizationGenerator,
    num_candidates: int,
    checker: EquivalenceChecker | None = None,
) -> OptimizationRunReport:
    checker = checker or EquivalenceChecker()
    original_ir = compile_source(source)

    raw_candidates = generator.generate_candidates(original_ir, num_candidates)

    reports: list[CandidateReport] = []
    for idx, raw_text in enumerate(raw_candidates):
        parsed = parse_candidate(raw_text, expected_name=original_ir.name)

        if not parsed.ok:
            reports.append(
                CandidateReport(
                    index=idx,
                    raw_text=raw_text,
                    parse_error=parsed.error_message,
                    candidate_ir=None,
                    decision=None,
                )
            )
            continue

        candidate_ir = parsed.ir_function
        verification = checker.verify(original_ir, candidate_ir)
        metrics = None
        if verification.status == VerificationStatus.EQUIVALENT:
            metrics = compute_optimization_metrics(original_ir, candidate_ir)

        reports.append(
            CandidateReport(
                index=idx,
                raw_text=raw_text,
                parse_error=None,
                candidate_ir=candidate_ir,
                decision=decide(verification, metrics),
            )
        )

    return OptimizationRunReport(original_ir=original_ir, candidates=reports, generator_name=generator.name)


def verify_pair(original_source: str, optimized_source: str, checker: EquivalenceChecker | None = None) -> dict:
    checker = checker or EquivalenceChecker()
    original_ir = compile_source(original_source)
    optimized_ir = compile_source(optimized_source)
    result: VerificationResult = checker.verify(original_ir, optimized_ir)
    return {
        "original_ir": IR.to_dict(original_ir),
        "optimized_ir": IR.to_dict(optimized_ir),
        "verification": result.to_dict(),
    }


def _summarize(candidates: list[CandidateReport]) -> dict:
    total = len(candidates)
    accepted = sum(1 for c in candidates if c.decision and c.decision.accepted)
    rejected_equivalence = sum(
        1
        for c in candidates
        if c.decision and not c.decision.accepted
    )
    parse_failures = sum(1 for c in candidates if c.parse_error is not None)
    return {
        "total_candidates": total,
        "accepted": accepted,
        "rejected": rejected_equivalence + parse_failures,
        "parse_failures": parse_failures,
        "acceptance_rate_pct": round(accepted / total * 100, 2) if total else 0.0,
    }
