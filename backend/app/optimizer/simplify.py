"""A small deterministic peephole optimizer.

This is NOT the "formal truth" of the system -- it exists so the mock
LLM generator can produce realistic, usually-correct optimization
candidates without needing a real model. Every candidate it produces
still goes through the Z3 equivalence checker like any other candidate;
nothing here is trusted directly.

Rules implemented:
  - constant folding:        2 + 3 -> 5
  - algebraic identities:    x+0->x, x-0->x, x*1->x, x*0->0, 0*x->0
  - strength "reduction":    x+x -> 2*x  (MUL by constant 2)
  - common subexpression elimination (CSE): identical instructions
    (same op + resolved operands) are collapsed to a single temp.
"""
from __future__ import annotations

from app.compiler import ir as IR


def _euclidean_mod(a: int, b: int) -> int:
    """SMT-LIB / Z3 semantics: 0 <= mod(a, b) < |b| for b != 0."""
    r = a % abs(b)
    return r


def _euclidean_div(a: int, b: int) -> int:
    r = _euclidean_mod(a, b)
    return (a - r) // b


def simplify(fn: IR.IRFunction) -> IR.IRFunction:
    alias: dict[str, IR.Operand] = {}  # old dest -> replacement operand (var, temp, or literal)
    cse_table: dict[tuple, str] = {}  # (op, resolved_lhs, resolved_rhs) -> existing dest
    new_instructions: list[IR.Instruction] = []

    def resolve(operand: IR.Operand) -> IR.Operand:
        seen = set()
        while isinstance(operand, str) and operand in alias:
            if operand in seen:
                break
            seen.add(operand)
            operand = alias[operand]
        return operand

    for instr in fn.instructions:
        if isinstance(instr, IR.ConstInstr):
            alias[instr.dest] = instr.value
            continue

        if isinstance(instr, IR.BinArithInstr):
            lhs = resolve(instr.lhs)
            rhs = resolve(instr.rhs)
            folded = _fold_arith(instr.op, lhs, rhs)
            if folded is not None:
                alias[instr.dest] = folded
                continue

            key = (instr.op, lhs, rhs)
            if key in cse_table:
                alias[instr.dest] = cse_table[key]
                continue

            # Strength "reduction": x + x -> 2 * x, expressed as a MUL.
            if instr.op == "ADD" and lhs == rhs and isinstance(lhs, str):
                mul_key = ("MUL", lhs, 2)
                if mul_key in cse_table:
                    alias[instr.dest] = cse_table[mul_key]
                else:
                    new_instructions.append(IR.BinArithInstr(op="MUL", dest=instr.dest, lhs=lhs, rhs=2))
                    cse_table[mul_key] = instr.dest
                continue

            new_instructions.append(IR.BinArithInstr(op=instr.op, dest=instr.dest, lhs=lhs, rhs=rhs))
            cse_table[key] = instr.dest

        elif isinstance(instr, IR.CmpInstr):
            lhs = resolve(instr.lhs)
            rhs = resolve(instr.rhs)
            key = ("CMP", instr.cmp, lhs, rhs)
            if key in cse_table:
                alias[instr.dest] = cse_table[key]
                continue
            new_instructions.append(IR.CmpInstr(dest=instr.dest, cmp=instr.cmp, lhs=lhs, rhs=rhs))
            cse_table[key] = instr.dest

        elif isinstance(instr, IR.SelectInstr):
            cond = resolve(instr.cond)
            then_val = resolve(instr.then_val)
            else_val = resolve(instr.else_val)
            if then_val == else_val:
                alias[instr.dest] = then_val
                continue
            new_instructions.append(
                IR.SelectInstr(dest=instr.dest, cond=cond, then_val=then_val, else_val=else_val)
            )

        elif isinstance(instr, IR.ReturnInstr):
            new_instructions.append(IR.ReturnInstr(value=resolve(instr.value)))

        else:
            new_instructions.append(instr)

    simplified = IR.IRFunction(name=fn.name, params=list(fn.params), instructions=new_instructions)
    IR.validate_ir(simplified)
    return simplified


def _fold_arith(op: str, lhs: IR.Operand, rhs: IR.Operand):
    """Return a replacement operand if this instruction can be eliminated, else None."""
    if isinstance(lhs, int) and isinstance(rhs, int):
        if op == "ADD":
            return lhs + rhs
        if op == "SUB":
            return lhs - rhs
        if op == "MUL":
            return lhs * rhs
        if op == "DIV" and rhs != 0:
            return _euclidean_div(lhs, rhs)
        if op == "MOD" and rhs != 0:
            return _euclidean_mod(lhs, rhs)
        return None

    if op == "ADD":
        if rhs == 0:
            return lhs
        if lhs == 0:
            return rhs
    if op == "SUB":
        if rhs == 0:
            return lhs
        if lhs == rhs:
            return 0
    if op == "MUL":
        if rhs == 1:
            return lhs
        if lhs == 1:
            return rhs
        if rhs == 0 or lhs == 0:
            return 0

    return None
