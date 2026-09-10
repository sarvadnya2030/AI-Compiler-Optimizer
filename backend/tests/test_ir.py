import pytest

from app.compiler import ir as IR
from app.compiler.lowering import LoweringError, lower_source


def test_ast_to_ir_basic():
    fn = lower_source("fn compute(x, y) { a = x * 2; b = y + 0; c = a + a; return c + b; }")
    ops = [i.op for i in fn.instructions]
    assert ops == ["MUL", "ADD", "ADD", "ADD", "RETURN"]
    assert fn.params == ["x", "y"]


def test_ir_is_ssa_unique_dests():
    fn = lower_source("fn f(x) { a = x + 1; a = a + 1; return a; }")
    dests = [i.dest for i in fn.instructions if hasattr(i, "dest")]
    assert len(dests) == len(set(dests))


def test_ir_roundtrip_json():
    fn = lower_source("fn f(x, y) { return x > y ? x : y; }")
    d = IR.to_dict(fn)
    fn2 = IR.from_dict(d)
    assert IR.to_dict(fn2) == d


def test_ir_serialization_matches_expected_shape():
    fn = lower_source("fn f(x) { a = x * 2; b = a + a; return b; }")
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
        lower_source("fn f(x, y) { return x > y; }")
