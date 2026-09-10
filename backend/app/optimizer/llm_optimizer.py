"""Optimization candidate generators.

    class OptimizationGenerator(ABC):
        def generate_candidates(program_ir, num_candidates) -> list[str]: ...

Every generator returns a list of *raw text* candidates (expected to be
JSON, possibly fenced) -- never parsed IR, never executed code. The
candidate_parser module is the only place raw text becomes IR, and it
runs the whitelisting validation in app.compiler.ir.
"""
from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod

import requests

from app.compiler import ir as IR
from app.optimizer.prompt_builder import SYSTEM_PROMPT, build_prompt
from app.optimizer.simplify import simplify

logger = logging.getLogger(__name__)


class OptimizationGenerator(ABC):
    @abstractmethod
    def generate_candidates(self, program_ir: IR.IRFunction, num_candidates: int) -> list[str]:
        """Return up to num_candidates raw-text (JSON) IR candidates."""
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError


class MockOptimizationGenerator(OptimizationGenerator):
    """Deterministic, offline generator.

    Produces (in order): the identity program, a peephole-simplified
    program, and then a rotating set of intentionally-broken mutations.
    This lets the whole ACCEPT/REJECT pipeline be demonstrated without
    any model running.
    """

    @property
    def name(self) -> str:
        return "mock"

    def generate_candidates(self, program_ir: IR.IRFunction, num_candidates: int) -> list[str]:
        candidates: list[dict] = []

        identity = IR.to_dict(program_ir)
        candidates.append(identity)

        try:
            simplified = simplify(program_ir)
            candidates.append(IR.to_dict(simplified))
        except Exception:
            logger.exception("mock simplifier failed; falling back to identity")

        mutations = _generate_invalid_mutations(program_ir)
        candidates.extend(mutations)

        # Pad by cycling if the caller asked for more than we produced.
        out: list[dict] = []
        i = 0
        while len(out) < num_candidates and candidates:
            out.append(candidates[i % len(candidates)])
            i += 1

        return [json.dumps(c) for c in out[:num_candidates]]


class OllamaOptimizationGenerator(OptimizationGenerator):
    """Talks to a local Ollama server's HTTP API."""

    def __init__(self, base_url: str, model: str, timeout_s: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_s = timeout_s

    @property
    def name(self) -> str:
        return f"ollama:{self.model}"

    def generate_candidates(self, program_ir: IR.IRFunction, num_candidates: int) -> list[str]:
        prompt = build_prompt(program_ir)
        results: list[str] = []
        for _ in range(num_candidates):
            try:
                results.append(self._generate_one(prompt))
            except (requests.RequestException, KeyError, ValueError) as e:
                logger.warning("Ollama generation failed: %s", e)
                results.append(json.dumps({"error": f"generation_failed: {e}"}))
        return results

    def _generate_one(self, prompt: str) -> str:
        response = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "format": "json",
            },
            timeout=self.timeout_s,
        )
        response.raise_for_status()
        data = response.json()
        return data["message"]["content"]


def _generate_invalid_mutations(program_ir: IR.IRFunction) -> list[dict]:
    """Produce plausible-but-wrong transformations, for demonstrating REJECT."""
    mutations: list[dict] = []

    for i, instr in enumerate(program_ir.instructions):
        if isinstance(instr, IR.BinArithInstr) and instr.op in ("ADD", "MUL"):
            wrong_op = "MUL" if instr.op == "ADD" else "ADD"
            mutated = list(program_ir.instructions)
            mutated[i] = IR.BinArithInstr(op=wrong_op, dest=instr.dest, lhs=instr.lhs, rhs=instr.rhs)
            candidate_fn = IR.IRFunction(name=program_ir.name, params=list(program_ir.params), instructions=mutated)
            mutations.append(IR.to_dict(candidate_fn))
            break

    for i, instr in enumerate(program_ir.instructions):
        if isinstance(instr, IR.BinArithInstr) and isinstance(instr.rhs, int):
            mutated = list(program_ir.instructions)
            mutated[i] = IR.BinArithInstr(op=instr.op, dest=instr.dest, lhs=instr.lhs, rhs=instr.rhs + 1)
            candidate_fn = IR.IRFunction(name=program_ir.name, params=list(program_ir.params), instructions=mutated)
            mutations.append(IR.to_dict(candidate_fn))
            break

    if not mutations:
        # Fallback mutation guaranteed to exist: return a constant 0 instead.
        mutated = list(program_ir.instructions[:-1]) + [IR.ReturnInstr(value=0)]
        candidate_fn = IR.IRFunction(name=program_ir.name, params=list(program_ir.params), instructions=mutated)
        mutations.append(IR.to_dict(candidate_fn))

    return mutations


def build_generator(
    mode: str, ollama_base_url: str = "", ollama_model: str = "", ollama_timeout_s: float = 60.0
) -> OptimizationGenerator:
    if mode == "mock":
        return MockOptimizationGenerator()
    if mode == "ollama":
        if not ollama_base_url or not ollama_model:
            raise ValueError("ollama_base_url and ollama_model are required for mode='ollama'")
        return OllamaOptimizationGenerator(base_url=ollama_base_url, model=ollama_model, timeout_s=ollama_timeout_s)
    raise ValueError(f"unknown generator mode: {mode!r}")
