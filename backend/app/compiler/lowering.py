"""Lowers a mini-C AST Function into a straight-line SSA IRFunction.

The interesting part is `if`/`else`. The IR has no branches -- only a
flat instruction list plus SELECT (a ternary). Statement-level if/else
is lowered via **tail duplication**: everything that comes *after* an
if/else in the same block is appended onto *both* branches before
recursing, so each branch independently computes "the value ultimately
returned given we took this path" -- and the two paths' final values are
combined with a single SELECT keyed on the branch condition.

Since the IR has no side effects, computing both branches unconditionally
(rather than actually branching) is semantics-preserving -- it mirrors
exactly how the ternary `cond ? a : b` already works, just generalized
from expressions to whole statement blocks. The cost is that instruction
count can grow with nesting depth (each nested if-with-fallthrough
duplicates everything after it into both arms) -- acceptable for a mini
compiler with small, loop-free programs; see docs/ir.md.
"""
from __future__ import annotations

from . import ast as A
from . import ir as IR

_CMP_MAP = {"==": "eq", "!=": "ne", "<": "lt", "<=": "le", ">": "gt", ">=": "ge"}


class LoweringError(Exception):
    pass


def _block_terminates(stmts: list[A.Stmt]) -> bool:
    """True if this block unconditionally returns on every path through it."""
    if not stmts:
        return False
    last = stmts[-1]
    if isinstance(last, A.Return):
        return True
    if isinstance(last, A.If):
        return (
            last.else_body is not None
            and _block_terminates(last.then_body)
            and _block_terminates(last.else_body)
        )
    return False


class _Lowerer:
    def __init__(self, params: list[str]):
        self.instructions: list[IR.Instruction] = []
        self.bool_temps: set[str] = set()
        self._counter = 0
        self._params = set(params)

    def _fresh_temp(self) -> str:
        self._counter += 1
        return f"t{self._counter}"

    def lower_function(self, fn: A.Function, params: list[str]) -> IR.IRFunction:
        env = {p: p for p in params}
        return_value = self._lower_block(fn.body, env)
        self.instructions.append(IR.ReturnInstr(value=return_value))
        return IR.IRFunction(name=fn.name, params=list(params), instructions=self.instructions)

    def _lower_block(self, stmts: list[A.Stmt], env: dict[str, IR.Operand]) -> IR.Operand:
        """Returns the operand for the value control returns along this path."""
        if not stmts:
            raise LoweringError("control path falls off the end of a block without returning")

        stmt, rest = stmts[0], stmts[1:]

        if isinstance(stmt, A.VarDecl):
            if stmt.name in env:
                raise LoweringError(f"redeclaration of variable {stmt.name!r}")
            value = self._lower_expr(stmt.value, env)
            new_env = dict(env)
            new_env[stmt.name] = value
            return self._lower_block(rest, new_env)

        if isinstance(stmt, A.Assign):
            if stmt.name not in env:
                raise LoweringError(f"assignment to undeclared variable {stmt.name!r}")
            value = self._lower_expr(stmt.value, env)
            new_env = dict(env)
            new_env[stmt.name] = value
            return self._lower_block(rest, new_env)

        if isinstance(stmt, A.Return):
            if rest:
                raise LoweringError("unreachable code after return")
            value = self._lower_expr(stmt.value, env)
            if isinstance(value, str) and value in self.bool_temps:
                raise LoweringError("cannot return a boolean (comparison) result directly")
            return value

        if isinstance(stmt, A.If):
            cond = self._lower_expr(stmt.cond, env)
            if not (isinstance(cond, str) and cond in self.bool_temps):
                raise LoweringError("if-condition must be a comparison")

            # Only splice `rest` onto a branch that doesn't already return on
            # every path -- a branch that already terminates must NOT see
            # `rest` (it would be unreachable dead code on that path).
            then_terminates = _block_terminates(stmt.then_body)
            then_val = self._lower_block(
                stmt.then_body if then_terminates else stmt.then_body + rest, dict(env)
            )

            if stmt.else_body is not None:
                else_terminates = _block_terminates(stmt.else_body)
                else_val = self._lower_block(
                    stmt.else_body if else_terminates else stmt.else_body + rest, dict(env)
                )
            else:
                else_terminates = False
                else_val = self._lower_block(rest, dict(env))

            if then_terminates and else_terminates and rest:
                raise LoweringError("unreachable code after an if/else where both branches return")

            dest = self._fresh_temp()
            self.instructions.append(IR.SelectInstr(dest=dest, cond=cond, then_val=then_val, else_val=else_val))
            return dest

        raise LoweringError(f"unsupported statement: {stmt!r}")

    def _lower_expr(self, expr: A.Expr, env: dict[str, IR.Operand]) -> IR.Operand:
        if isinstance(expr, A.NumberLit):
            return expr.value

        if isinstance(expr, A.VarRef):
            if expr.name not in env:
                raise LoweringError(f"use of undefined variable {expr.name!r}")
            return env[expr.name]

        if isinstance(expr, A.UnaryOp):
            if expr.op == "-":
                # Lower -e as (0 - e) -- keeps the IR op set minimal.
                operand = self._lower_expr(expr.operand, env)
                dest = self._fresh_temp()
                self.instructions.append(IR.BinArithInstr(op="SUB", dest=dest, lhs=0, rhs=operand))
                return dest
            raise LoweringError(f"unsupported unary operator {expr.op!r}")

        if isinstance(expr, A.BinOp):
            lhs = self._lower_expr(expr.left, env)
            rhs = self._lower_expr(expr.right, env)
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
            cond = self._lower_expr(expr.cond, env)
            if not (isinstance(cond, str) and cond in self.bool_temps):
                raise LoweringError("conditional expression's condition must be a comparison")
            then_val = self._lower_expr(expr.then_expr, env)
            else_val = self._lower_expr(expr.else_expr, env)
            dest = self._fresh_temp()
            self.instructions.append(
                IR.SelectInstr(dest=dest, cond=cond, then_val=then_val, else_val=else_val)
            )
            return dest

        raise LoweringError(f"unsupported expression: {expr!r}")


def lower_function(fn: A.Function) -> IR.IRFunction:
    ir_fn = _Lowerer(fn.params).lower_function(fn, fn.params)
    IR.validate_ir(ir_fn)
    return ir_fn


def lower_source(source: str) -> IR.IRFunction:
    from .parser import parse_function

    return lower_function(parse_function(source))
