"""The IR (intermediate representation).

A restricted, explicit instruction set over mathematical integers.
Every temporary gets a unique SSA-style name (t1, t2, ...). Instructions
are immutable dataclasses; an IRFunction is just an ordered instruction
list plus a parameter list.

Supported ops: CONST, ADD, SUB, MUL, DIV, MOD, CMP, SELECT, RETURN.

CMP produces a boolean-typed temporary; SELECT and everything else is
integer-typed. RETURN must reference an integer-typed value.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Union

Operand = Union[str, int]  # str -> reference to a temp/param name, int -> literal

ARITH_OPS = ("ADD", "SUB", "MUL", "DIV", "MOD")
CMP_OPS = ("eq", "ne", "lt", "le", "gt", "ge")


class IRValidationError(Exception):
    pass


@dataclass(frozen=True)
class ConstInstr:
    dest: str
    value: int
    op: str = field(default="CONST", init=False)


@dataclass(frozen=True)
class BinArithInstr:
    op: str  # one of ARITH_OPS
    dest: str
    lhs: Operand
    rhs: Operand


@dataclass(frozen=True)
class CmpInstr:
    dest: str
    cmp: str  # one of CMP_OPS
    lhs: Operand
    rhs: Operand
    op: str = field(default="CMP", init=False)


@dataclass(frozen=True)
class SelectInstr:
    dest: str
    cond: Operand
    then_val: Operand
    else_val: Operand
    op: str = field(default="SELECT", init=False)


@dataclass(frozen=True)
class ReturnInstr:
    value: Operand
    op: str = field(default="RETURN", init=False)


Instruction = Union[ConstInstr, BinArithInstr, CmpInstr, SelectInstr, ReturnInstr]


@dataclass
class IRFunction:
    name: str
    params: List[str]
    instructions: List[Instruction]


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def instruction_to_dict(instr: Instruction) -> dict:
    if isinstance(instr, ConstInstr):
        return {"op": "CONST", "dest": instr.dest, "value": instr.value}
    if isinstance(instr, BinArithInstr):
        return {"op": instr.op, "dest": instr.dest, "lhs": instr.lhs, "rhs": instr.rhs}
    if isinstance(instr, CmpInstr):
        return {"op": "CMP", "dest": instr.dest, "cmp": instr.cmp, "lhs": instr.lhs, "rhs": instr.rhs}
    if isinstance(instr, SelectInstr):
        return {
            "op": "SELECT",
            "dest": instr.dest,
            "cond": instr.cond,
            "then": instr.then_val,
            "else": instr.else_val,
        }
    if isinstance(instr, ReturnInstr):
        return {"op": "RETURN", "value": instr.value}
    raise IRValidationError(f"unknown instruction type: {instr!r}")


def to_dict(fn: IRFunction) -> dict:
    return {
        "name": fn.name,
        "params": list(fn.params),
        "instructions": [instruction_to_dict(i) for i in fn.instructions],
    }


def instruction_from_dict(d: dict) -> Instruction:
    if not isinstance(d, dict) or "op" not in d:
        raise IRValidationError(f"instruction must be an object with an 'op' field, got: {d!r}")
    op = d["op"]

    if op == "CONST":
        _require_fields(d, ["dest", "value"], op)
        _require_type(d["dest"], str, "dest", op)
        _require_type(d["value"], int, "value", op)
        return ConstInstr(dest=d["dest"], value=d["value"])

    if op in ARITH_OPS:
        _require_fields(d, ["dest", "lhs", "rhs"], op)
        _require_type(d["dest"], str, "dest", op)
        lhs = _require_operand(d["lhs"], "lhs", op)
        rhs = _require_operand(d["rhs"], "rhs", op)
        return BinArithInstr(op=op, dest=d["dest"], lhs=lhs, rhs=rhs)

    if op == "CMP":
        _require_fields(d, ["dest", "cmp", "lhs", "rhs"], op)
        _require_type(d["dest"], str, "dest", op)
        if d["cmp"] not in CMP_OPS:
            raise IRValidationError(f"CMP.cmp must be one of {CMP_OPS}, got {d['cmp']!r}")
        lhs = _require_operand(d["lhs"], "lhs", op)
        rhs = _require_operand(d["rhs"], "rhs", op)
        return CmpInstr(dest=d["dest"], cmp=d["cmp"], lhs=lhs, rhs=rhs)

    if op == "SELECT":
        _require_fields(d, ["dest", "cond", "then", "else"], op)
        _require_type(d["dest"], str, "dest", op)
        cond = _require_operand(d["cond"], "cond", op)
        then_val = _require_operand(d["then"], "then", op)
        else_val = _require_operand(d["else"], "else", op)
        return SelectInstr(dest=d["dest"], cond=cond, then_val=then_val, else_val=else_val)

    if op == "RETURN":
        _require_fields(d, ["value"], op)
        value = _require_operand(d["value"], "value", op)
        return ReturnInstr(value=value)

    raise IRValidationError(
        f"unsupported IR op {op!r}; supported ops are CONST, {', '.join(ARITH_OPS)}, CMP, SELECT, RETURN"
    )


def from_dict(d: dict) -> IRFunction:
    if not isinstance(d, dict):
        raise IRValidationError("IR function must be a JSON object")
    name = d.get("name", "candidate")
    params = d.get("params", [])
    if not isinstance(params, list) or not all(isinstance(p, str) for p in params):
        raise IRValidationError("'params' must be a list of strings")
    raw_instructions = d.get("instructions")
    if not isinstance(raw_instructions, list):
        raise IRValidationError("'instructions' must be a list")
    instructions = [instruction_from_dict(i) for i in raw_instructions]
    fn = IRFunction(name=name, params=params, instructions=instructions)
    validate_ir(fn)
    return fn


def _require_fields(d: dict, fields_: list[str], op: str) -> None:
    missing = [f for f in fields_ if f not in d]
    if missing:
        raise IRValidationError(f"{op} instruction missing required field(s): {missing}")


def _require_type(value, expected_type, field_name: str, op: str) -> None:
    if expected_type is int and isinstance(value, bool):
        raise IRValidationError(f"{op}.{field_name} must be an int, got bool")
    if not isinstance(value, expected_type):
        raise IRValidationError(f"{op}.{field_name} must be a {expected_type.__name__}, got {type(value).__name__}")


def _require_operand(value, field_name: str, op: str) -> Operand:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise IRValidationError(f"{op}.{field_name} must be a string (reference) or int (literal), got {value!r}")
    return value


# ---------------------------------------------------------------------------
# Validation: every referenced name must be defined earlier (param or dest),
# every dest must be unique (true SSA), and the function must end in RETURN.
# ---------------------------------------------------------------------------

def validate_ir(fn: IRFunction) -> None:
    defined = set(fn.params)
    bool_typed: set[str] = set()

    if not fn.instructions:
        raise IRValidationError("IR function must contain at least one instruction")

    for idx, instr in enumerate(fn.instructions):
        is_last = idx == len(fn.instructions) - 1

        if isinstance(instr, ReturnInstr):
            if not is_last:
                raise IRValidationError("RETURN must be the final instruction")
            _check_ref(instr.value, defined, "RETURN.value")
            if _ref_name(instr.value) in bool_typed:
                raise IRValidationError("RETURN.value must be integer-typed, not a CMP result")
            continue

        if is_last:
            raise IRValidationError("the last instruction of a function must be RETURN")

        if instr.dest in defined:
            raise IRValidationError(f"duplicate definition of temp/variable {instr.dest!r} (IR must be SSA)")

        if isinstance(instr, ConstInstr):
            pass
        elif isinstance(instr, BinArithInstr):
            _check_ref(instr.lhs, defined, f"{instr.op}.lhs")
            _check_ref(instr.rhs, defined, f"{instr.op}.rhs")
            for operand in (instr.lhs, instr.rhs):
                if _ref_name(operand) in bool_typed:
                    raise IRValidationError(f"{instr.op} operand {operand!r} is boolean-typed (from CMP)")
        elif isinstance(instr, CmpInstr):
            _check_ref(instr.lhs, defined, "CMP.lhs")
            _check_ref(instr.rhs, defined, "CMP.rhs")
            bool_typed.add(instr.dest)
        elif isinstance(instr, SelectInstr):
            _check_ref(instr.cond, defined, "SELECT.cond")
            if _ref_name(instr.cond) not in bool_typed:
                raise IRValidationError("SELECT.cond must reference a CMP result")
            _check_ref(instr.then_val, defined, "SELECT.then")
            _check_ref(instr.else_val, defined, "SELECT.else")
        else:
            raise IRValidationError(f"unsupported instruction in validation: {instr!r}")

        defined.add(instr.dest)


def _ref_name(operand: Operand):
    return operand if isinstance(operand, str) else None


def _check_ref(operand: Operand, defined: set[str], where: str) -> None:
    if isinstance(operand, int):
        return
    if operand not in defined:
        raise IRValidationError(f"{where} references undefined name {operand!r}")
