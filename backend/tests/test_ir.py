import pytest

from app.compiler import ir as IR
from app.compiler.lowering import LoweringError, lower_source


def test_ast_to_ir_basic():
    fn = lower_source("int compute(int x, int y) { int a = x * 2; int b = y + 0; int c = a + a; return c + b; }")
    ops = [i.op for i in fn.instructions]
    assert ops == ["MUL", "ADD", "ADD", "ADD", "RETURN"]
    assert fn.params == ["x", "y"]


def test_ir_is_ssa_unique_dests():
    fn = lower_source("int f(int x) { int a = x + 1; int b = a + 1; return b; }")
    dests = [i.dest for i in fn.instructions if hasattr(i, "dest")]
    assert len(dests) == len(set(dests))


def test_ir_roundtrip_json():
    fn = lower_source("int f(int x, int y) { return x > y ? x : y; }")
    d = IR.to_dict(fn)
    fn2 = IR.from_dict(d)
    assert IR.to_dict(fn2) == d


def test_ir_serialization_matches_expected_shape():
    fn = lower_source("int f(int x) { int a = x * 2; int b = a + a; return b; }")
    d = IR.to_dict(fn)
    assert d["instructions"][0] == {"op": "MUL", "dest": "t1", "lhs": "x", "rhs": 2}


def test_ir_rejects_unsupported_op():
    with pytest.raises(IR.IRValidationError):
        IR.from_dict({"name": "f", "params": ["x"], "instructions": [{"op": "SHL", "dest": "t1", "lhs": "x", "rhs": 1}]})


def test_ir_rejects_undefined_reference():
    with pytest.raises(IR.IRValidationError):
        IR.from_dict({"name": "f", "params": ["x"], "instructions": [{"op": "RETURN", "value": "undefined_var"}]})


def test_ir_rejects_missing_return():
    with pytest.raises(IR.IRValidationError):
        IR.from_dict({"name": "f", "params": ["x"], "instructions": [{"op": "ADD", "dest": "t1", "lhs": "x", "rhs": 1}]})


def test_ir_rejects_duplicate_dest():
    with pytest.raises(IR.IRValidationError):
        IR.from_dict(
            {
                "name": "f",
                "params": ["x"],
                "instructions": [
                    {"op": "ADD", "dest": "t1", "lhs": "x", "rhs": 1},
                    {"op": "ADD", "dest": "t1", "lhs": "x", "rhs": 2},
                    {"op": "RETURN", "value": "t1"},
                ],
            }
        )


def test_ir_rejects_select_with_non_cmp_cond():
    with pytest.raises(IR.IRValidationError):
        IR.from_dict(
            {
                "name": "f",
                "params": ["x"],
                "instructions": [
                    {"op": "SELECT", "dest": "t1", "cond": "x", "then": "x", "else": 0},
                    {"op": "RETURN", "value": "t1"},
                ],
            }
        )


def test_lowering_rejects_returning_a_bare_comparison():
    with pytest.raises(LoweringError):
        lower_source("int f(int x, int y) { return x > y; }")


def test_lowering_rejects_redeclaration():
    with pytest.raises(LoweringError):
        lower_source("int f(int x) { int a = x; int a = x + 1; return a; }")


def test_lowering_rejects_assignment_to_undeclared_variable():
    with pytest.raises(LoweringError):
        lower_source("int f(int x) { a = x + 1; return a; }")


def test_lowering_rejects_unreachable_code_after_full_if_else():
    with pytest.raises(LoweringError):
        lower_source("int f(int x) { if (x > 0) { return 1; } else { return 0; } return 99; }")


def test_lowering_if_else_produces_select():
    fn = lower_source("int f(int x, int y) { if (x > y) { return x; } else { return y; } }")
    ops = [i.op for i in fn.instructions]
    assert ops == ["CMP", "SELECT", "RETURN"]


def test_lowering_early_return_fallthrough():
    fn = lower_source("int f(int x) { if (x < 0) { return 0 - x; } return x; }")
    ops = [i.op for i in fn.instructions]
    # cond, negate, select, return -- the fallthrough path is folded via SELECT
    assert ops == ["CMP", "SUB", "SELECT", "RETURN"]
