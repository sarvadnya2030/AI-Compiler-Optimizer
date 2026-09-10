"""Parses/validates raw LLM (or mock) output into IRFunction candidates.

This is the security boundary described in docs/verification.md: LLM
output is treated as untrusted JSON text. It is never executed, never
eval()'d -- only parsed as data and run through app.compiler.ir.from_dict,
which whitelists instruction shapes and operand types.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from app.compiler import ir as IR


@dataclass
class CandidateParseResult:
    ok: bool
    ir_function: IR.IRFunction | None
    raw_text: str
    error_message: str | None = None


def parse_candidate(raw_text: str, expected_name: str | None = None) -> CandidateParseResult:
    """Parse a JSON IR blob emitted by an optimization generator.

    Never raises for malformed input -- malformed candidates are simply
    unparseable and get reported/rejected upstream, never treated as
    equivalent by default.
    """
    text = _strip_code_fences(raw_text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return CandidateParseResult(ok=False, ir_function=None, raw_text=raw_text, error_message=f"invalid JSON: {e}")

    try:
        ir_fn = IR.from_dict(data)
    except IR.IRValidationError as e:
        return CandidateParseResult(ok=False, ir_function=None, raw_text=raw_text, error_message=str(e))

    if expected_name and ir_fn.name != expected_name:
        # Non-fatal: candidates may be generated without preserving the name.
        ir_fn.name = expected_name

    return CandidateParseResult(ok=True, ir_function=ir_fn, raw_text=raw_text)


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines)
    return stripped.strip()
