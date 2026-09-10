import z3

from app.compiler.lowering import lower_source
from app.verifier.z3_encoder import Z3Encoder


def _prove_identity(source_a: str, source_b: str) -> bool:
    """True iff the two single-param-set programs are provably equal for all inputs."""
    enc = Z3Encoder()
    a = enc.encode(lower_source(source_a))
    b = enc.encode(lower_source(source_b))
    solver = z3.Solver()
    solver.add(a.return_expr != b.return_expr)
    return solver.check() == z3.unsat


def test_x_plus_zero_equals_x():
    assert _prove_identity("fn f(x) { return x + 0; }", "fn f(x) { return x; }")


def test_x_times_one_equals_x():
    assert _prove_identity("fn f(x) { return x * 1; }", "fn f(x) { return x; }")


def test_x_plus_x_equals_two_x():
    assert _prove_identity("fn f(x) { return x + x; }", "fn f(x) { return 2 * x; }")


def test_x_times_x_not_equal_two_x():
    assert not _prove_identity("fn f(x) { return x * x; }", "fn f(x) { return 2 * x; }")


def test_x_plus_one_not_equal_x():
    assert not _prove_identity("fn f(x) { return x + 1; }", "fn f(x) { return x; }")


def test_encoder_handles_select():
    enc = Z3Encoder()
    result = enc.encode(lower_source("fn f(x, y) { return x > y ? x : y; }"))
    solver = z3.Solver()
    x, y = result.params["x"], result.params["y"]
    solver.add(x == 3, y == 7)
    solver.add(result.return_expr != 7)
    assert solver.check() == z3.unsat
