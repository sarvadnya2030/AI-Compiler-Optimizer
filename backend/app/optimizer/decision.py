"""The final accept/reject decision for one candidate.

Acceptance is derived from the verifier's output ONLY -- the LLM's
opinion of its own candidate plays no role.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.metrics.optimization_metrics import OptimizationMetrics
from app.verifier.equivalence import VerificationResult, VerificationStatus


@dataclass
class OptimizationDecision:
    accepted: bool
    verification: VerificationResult
    metrics: OptimizationMetrics | None

    def to_dict(self) -> dict:
        return {
            "accepted": self.accepted,
            "verification": self.verification.to_dict(),
            "metrics": self.metrics.to_dict() if self.metrics else None,
        }


def decide(verification: VerificationResult, metrics: OptimizationMetrics | None) -> OptimizationDecision:
    accepted = verification.status == VerificationStatus.EQUIVALENT
    return OptimizationDecision(accepted=accepted, verification=verification, metrics=metrics)
