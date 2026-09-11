from app.compiler.lowering import lower_source
from app.verifier.equivalence import EquivalenceChecker, VerificationStatus


def test_equivalent_pair_returns_equivalent():
    checker = EquivalenceChecker()
    original = lower_source("int f(int x) { return x + 0; }")
    optimized = lower_source("int f(int x) { return x; }")
    result = checker.verify(original, optimized)
    assert result.status == VerificationStatus.EQUIVALENT
    assert result.z3_result == "unsat"
    assert result.counterexample is None


def test_non_equivalent_pair_returns_not_equivalent_with_counterexample():
    checker = EquivalenceChecker()
    original = lower_source("int f(int x) { return x * x; }")
    optimized = lower_source("int f(int x) { return 2 * x; }")
    result = checker.verify(original, optimized)
    assert result.status == VerificationStatus.NOT_EQUIVALENT
    assert result.z3_result == "sat"
    assert result.counterexample is not None

    x = result.counterexample.inputs["x"]
    assert result.counterexample.original_output == x * x
    assert result.counterexample.optimized_output == 2 * x
    assert result.counterexample.original_output != result.counterexample.optimized_output


def test_multi_step_equivalent_optimization():
    checker = EquivalenceChecker()
    original = lower_source(
        "int f(int x) { int t1 = x + 0; int t2 = t1 * 1; int t3 = t2 + t2; return t3; }"
    )
    optimized = lower_source("int f(int x) { return x * 2; }")
    result = checker.verify(original, optimized)
    assert result.status == VerificationStatus.EQUIVALENT


def test_verification_time_is_measured():
    checker = EquivalenceChecker()
    original = lower_source("int f(int x) { return x; }")
    optimized = lower_source("int f(int x) { return x; }")
    result = checker.verify(original, optimized)
    assert result.verification_time_ms >= 0


def test_signature_mismatch_is_not_sent_to_z3_as_equivalent():
    checker = EquivalenceChecker()
    original = lower_source("int f(int x) { return x; }")
    optimized = lower_source("int f(int z) { return z; }")
    result = checker.verify(original, optimized)
    assert result.status == VerificationStatus.SIGNATURE_MISMATCH
