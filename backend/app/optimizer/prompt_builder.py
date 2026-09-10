"""Builds the prompt sent to a real LLM backend (e.g. Ollama).

The prompt is deliberately restrictive: it lists the exact supported
ops and demands a single JSON object back, matching the IR schema in
app.compiler.ir. The LLM is never told its output will be trusted --
on the contrary, the system prompt makes clear a verifier will check it.
"""
from __future__ import annotations

import json

from app.compiler import ir as IR

SUPPORTED_OPS = ["CONST", "ADD", "SUB", "MUL", "DIV", "MOD", "CMP", "SELECT", "RETURN"]

SYSTEM_PROMPT = """You are an optimizing compiler pass. You propose optimized versions of a \
given intermediate representation (IR) program. You do NOT decide correctness: every \
candidate you produce will be independently checked for semantic equivalence by a formal \
verifier (Z3). Focus on producing a plausible, smaller-or-equal-cost equivalent program.

Only use these IR instruction ops: CONST, ADD, SUB, MUL, DIV, MOD, CMP, SELECT, RETURN.
Do not invent new ops. Do not use pointers, arrays, structs, I/O, function calls, or loops.
Respond with ONLY a single JSON object matching the schema below -- no prose, no markdown \
fences, no explanation."""

_SCHEMA_EXAMPLE = {
    "name": "example",
    "params": ["x", "y"],
    "instructions": [
        {"op": "MUL", "dest": "t1", "lhs": "x", "rhs": 2},
        {"op": "ADD", "dest": "t2", "lhs": "t1", "rhs": "t1"},
        {"op": "RETURN", "value": "t2"},
    ],
}


def build_prompt(program_ir: IR.IRFunction, objective: str = "minimize instruction count") -> str:
    ir_json = json.dumps(IR.to_dict(program_ir), indent=2)
    schema_json = json.dumps(_SCHEMA_EXAMPLE, indent=2)

    return f"""Given this IR program:

{ir_json}

Supported operations:
{", ".join(SUPPORTED_OPS)}

Optimization objective: {objective}

Requirements:
- The optimized program MUST accept the same parameters: {program_ir.params}
- Do not change program semantics; only change how the result is computed.
- Return ONLY valid JSON with this exact shape (this is an example, not the answer):

{schema_json}

Return ONLY the JSON object for the optimized version of the given program. No other text."""
