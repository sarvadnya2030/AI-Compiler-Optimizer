"""Reusable counterexample representation."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Counterexample:
    """A concrete input assignment under which the two programs disagree."""
    inputs: dict[str, int]
    original_output: int
    optimized_output: int

    def to_dict(self) -> dict:
        return {
            "inputs": self.inputs,
            "original_output": self.original_output,
            "optimized_output": self.optimized_output,
        }
