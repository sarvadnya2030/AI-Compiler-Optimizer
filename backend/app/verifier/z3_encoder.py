"""Translates an IRFunction into a Z3 symbolic expression.

Every function parameter becomes a free Z3 Int. Every instruction is
evaluated in order, building up a dict of name -> Z3 expression (Int or
Bool sort). The encoder returns the symbolic expression for the
function's RETURN value plus the map of parameter name -> Z3 Int, so
callers can relate two encodings that share the same parameter names.

Division/modulo use Z3's native integer Div/Mod (SMT-LIB / Euclidean
semantics: for b != 0 there is a unique q, r with a = b*q + r and
0 <= r < |b|). Division by zero is *not* specially handled -- Z3 leaves
it as an underspecified but fixed value, consistent within one model.
This is a known limitation; see docs/verification.md.
"""
from __future__ import annotations

from dataclasses import dataclass

import z3

from app.compiler import ir as IR


class EncodingError(Exception):
    pass


@dataclass
class EncodedFunction:
    return_expr: "z3.ExprRef"
    params: dict[str, "z3.ExprRef"]
    solver_side_conditions: list["z3.BoolRef"]


class Z3Encoder:
    """Encodes a single IRFunction into a symbolic Z3 expression."""

    def encode(self, fn: IR.IRFunction) -> EncodedFunction:
        env: dict[str, "z3.ExprRef"] = {}
        params: dict[str, "z3.ExprRef"] = {}

        for name in fn.params:
            var = z3.Int(name)
            env[name] = var
            params[name] = var

        return_expr = None

        for instr in fn.instructions:
            if isinstance(instr, IR.ConstInstr):
                env[instr.dest] = z3.IntVal(instr.value)

            elif isinstance(instr, IR.BinArithInstr):
                lhs = self._resolve(instr.lhs, env)
                rhs = self._resolve(instr.rhs, env)
                env[instr.dest] = self._apply_arith(instr.op, lhs, rhs)

            elif isinstance(instr, IR.CmpInstr):
                lhs = self._resolve(instr.lhs, env)
                rhs = self._resolve(instr.rhs, env)
                env[instr.dest] = self._apply_cmp(instr.cmp, lhs, rhs)

            elif isinstance(instr, IR.SelectInstr):
                cond = self._resolve(instr.cond, env)
                then_val = self._resolve(instr.then_val, env)
                else_val = self._resolve(instr.else_val, env)
                env[instr.dest] = z3.If(cond, then_val, else_val)

            elif isinstance(instr, IR.ReturnInstr):
                return_expr = self._resolve(instr.value, env)

            else:
                raise EncodingError(f"unsupported instruction: {instr!r}")

        if return_expr is None:
            raise EncodingError("IR function has no RETURN instruction")

        return EncodedFunction(return_expr=return_expr, params=params, solver_side_conditions=[])

    @staticmethod
    def _resolve(operand: IR.Operand, env: dict[str, "z3.ExprRef"]):
        if isinstance(operand, int):
            return z3.IntVal(operand)
        if operand not in env:
            raise EncodingError(f"reference to undefined name {operand!r} during encoding")
        return env[operand]

    @staticmethod
    def _apply_arith(op: str, lhs, rhs):
        if op == "ADD":
            return lhs + rhs
        if op == "SUB":
            return lhs - rhs
        if op == "MUL":
            return lhs * rhs
        if op == "DIV":
            return lhs / rhs
        if op == "MOD":
            return lhs % rhs
        raise EncodingError(f"unsupported arithmetic op: {op!r}")

    @staticmethod
    def _apply_cmp(cmp: str, lhs, rhs):
        if cmp == "eq":
            return lhs == rhs
        if cmp == "ne":
            return lhs != rhs
        if cmp == "lt":
            return lhs < rhs
        if cmp == "le":
            return lhs <= rhs
        if cmp == "gt":
            return lhs > rhs
        if cmp == "ge":
            return lhs >= rhs
        raise EncodingError(f"unsupported comparison: {cmp!r}")
