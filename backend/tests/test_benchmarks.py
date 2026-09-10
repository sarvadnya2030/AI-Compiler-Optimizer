"""Cross-checks the benchmark suite itself against the real Z3 verifier.

This guards against a benchmark's expected_properties silently going
stale (e.g. after an IR/encoder change) instead of reflecting ground truth.
"""
from app.api.benchmarks_loader import load_all_benchmarks
from app.optimizer.pipeline import compile_source
from app.verifier.equivalence import EquivalenceChecker, VerificationStatus

_CHECKER = EquivalenceChecker()


def test_benchmark_suite_has_at_least_30_programs():
    assert len(load_all_benchmarks()) >= 30


def test_benchmark_suite_covers_both_equivalent_and_non_equivalent_cases():
    records = load_all_benchmarks()
    flags = [r["expected_properties"]["candidate_equivalent"] for r in records]
    assert True in flags
    assert False in flags


def test_every_benchmark_candidate_matches_z3_ground_truth():
    for record in load_all_benchmarks():
        original = compile_source(record["program"])
        candidate = compile_source(record["candidate_program"])
        result = _CHECKER.verify(original, candidate)
        expected = record["expected_properties"]["candidate_equivalent"]
        actual = result.status == VerificationStatus.EQUIVALENT
        assert actual == expected, f"{record['id']}: expected candidate_equivalent={expected}, Z3 said {result.status}"
