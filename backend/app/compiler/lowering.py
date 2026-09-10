"""Lowers an AST Function into an SSA-like IRFunction.

Source-level variables may be reassigned (a = ...; a = ...); each
reassignment simply rebinds the source name to a fresh IR temp in the
lowering environment, which is what keeps the emitted IR itself in true
SSA form (every IR dest is defined exactly once).
"""
from __future__ import annotations

from . import ast as A
from . import ir as IR

_CMP_MAP = {"==": "eq", "!=": "ne", "<": "lt", "<=": "le", ">": "gt", ">=": "ge"}


class LoweringError(Exception):
    pass


class _Lowerer:
    def __init__(self, params: list[str]):
        self.instructions: list[IR.Instruction] = []
        self.env: dict[str, IR.Operand] = {p: p for p in params}
        self.bool_temps: set[str] = set()
        self._counter = 0

    def _fresh_temp(self) -> str:
        self._counter += 1
        return f"t{self._counter}"

    def lower_function(self, fn: A.Function) -> IR.IRFunction:
        for stmt in fn.body:
            self._lower_stmt(stmt)
        return IR.IRFunction(name=fn.name, params=list(fn.params), instructions=self.instructions)

    def _lower_stmt(self, stmt: A.Stmt) -> None:
        if isinstance(stmt, A.Assignment):
            value = self._lower_expr(stmt.value)
            self.env[stmt.name] = value
            return
        if isinstance(stmt, A.Return):
            value = self._lower_expr(stmt.value)
            if isinstance(value, str) and value in self.bool_temps:
                raise LoweringError("cannot return a boolean (comparison) result directly")
            self.instructions.append(IR.ReturnInstr(value=value))
            return
        raise LoweringError(f"unsupported statement: {stmt!r}")

    def _lower_expr(self, expr: A.Expr) -> IR.Operand:
        if isinstance(expr, A.NumberLit):
            return expr.value

        if isinstance(expr, A.VarRef):
            if expr.name not in self.env:
                raise LoweringError(f"use of undefined variable {expr.name!r}")
            return self.env[expr.name]

        if isinstance(expr, A.UnaryOp):
            if expr.op == "-":
                # Lower -e as (0 - e) -- keeps the IR op set minimal.
                operand = self._lower_expr(expr.operand)
                dest = self._fresh_temp()
                self.instructions.append(IR.BinArithInstr(op="SUB", dest=dest, lhs=0, rhs=operand))
                return dest
            raise LoweringError(f"unsupported unary operator {expr.op!r}")

        if isinstance(expr, A.BinOp):
            lhs = self._lower_expr(expr.left)
            rhs = self._lower_expr(expr.right)
            dest = self._fresh_temp()

            if expr.op in ("+", "-", "*", "/", "%"):
                op = {"+": "ADD", "-": "SUB", "*": "MUL", "/": "DIV", "%": "MOD"}[expr.op]
                self.instructions.append(IR.BinArithInstr(op=op, dest=dest, lhs=lhs, rhs=rhs))
                return dest

            if expr.op in _CMP_MAP:
                self.instructions.append(IR.CmpInstr(dest=dest, cmp=_CMP_MAP[expr.op], lhs=lhs, rhs=rhs))
                self.bool_temps.add(dest)
                return dest

            raise LoweringError(f"unsupported binary operator {expr.op!r}")

        if isinstance(expr, A.Conditional):
            cond = self._lower_expr(expr.cond)
            if not (isinstance(cond, str) and cond in self.bool_temps):
                raise LoweringError("conditional expression's condition must be a comparison")
            then_val = self._lower_expr(expr.then_expr)
            else_val = self._lower_expr(expr.else_expr)
            dest = self._fresh_temp()
            self.instructions.append(
                IR.SelectInstr(dest=dest, cond=cond, then_val=then_val, else_val=else_val)
            )
            return dest

        raise LoweringError(f"unsupported expression: {expr!r}")


def lower_function(fn: A.Function) -> IR.IRFunction:
    ir_fn = _Lowerer(fn.params).lower_function(fn)
    IR.validate_ir(ir_fn)
    return ir_fn


def lower_source(source: str) -> IR.IRFunction:
    from .parser import parse_function

    return lower_function(parse_function(source))
