import json

from app.compiler.lowering import lower_source
from app.optimizer.candidate_parser import parse_candidate
from app.optimizer.llm_optimizer import MockOptimizationGenerator
from app.optimizer.pipeline import run_optimization
from app.optimizer.simplify import simplify
from app.verifier.equivalence import VerificationStatus


def test_mock_generator_is_deterministic():
    gen = MockOptimizationGenerator()
    fn = lower_source("int f(int x) { int t1 = x + 0; return t1; }")
    a = gen.generate_candidates(fn, 3)
    b = gen.generate_candidates(fn, 3)
    assert a == b


def test_mock_generator_respects_num_candidates():
    gen = MockOptimizationGenerator()
    fn = lower_source("int f(int x) { return x + 0; }")
    candidates = gen.generate_candidates(fn, 5)
    assert len(candidates) == 5


def test_mock_generator_produces_both_valid_and_invalid_candidates():
    gen = MockOptimizationGenerator()
    fn = lower_source("int f(int x) { int t1 = x + 0; int t2 = t1 * 1; return t2 + t2; }")
    report = run_optimization("int f(int x) { int t1 = x + 0; int t2 = t1 * 1; return t2 + t2; }", gen, 4)
    statuses = [c.decision.verification.status for c in report.candidates if c.decision]
    assert VerificationStatus.EQUIVALENT in statuses
    assert VerificationStatus.NOT_EQUIVALENT in statuses


def test_candidate_parser_rejects_malformed_json():
    result = parse_candidate("not json at all")
    assert not result.ok
    assert result.ir_function is None


def test_candidate_parser_strips_code_fences():
    fn = lower_source("int f(int x) { return x; }")
    from app.compiler import ir as IR

    fenced = "```json\n" + json.dumps(IR.to_dict(fn)) + "\n```"
    result = parse_candidate(fenced)
    assert result.ok
    assert result.ir_function is not None


def test_candidate_parser_rejects_unsupported_op():
    bad = json.dumps({"name": "f", "params": ["x"], "instructions": [{"op": "SYSCALL", "dest": "t1"}]})
    result = parse_candidate(bad)
    assert not result.ok


def test_simplify_folds_constants_and_identities():
    fn = lower_source("int f(int x) { int a = x + 0; int b = a * 1; int c = 2 + 3; return b + c; }")
    simplified = simplify(fn)
    assert len(simplified.instructions) < len(fn.instructions)


def test_simplify_preserves_semantics():
    from app.verifier.equivalence import EquivalenceChecker

    fn = lower_source("int f(int x) { int a = x + 0; int b = a * 1; int c = b + b; return c; }")
    simplified = simplify(fn)
    checker = EquivalenceChecker()
    result = checker.verify(fn, simplified)
    assert result.status == VerificationStatus.EQUIVALENT


def test_pipeline_end_to_end_with_mock_generator():
    report = run_optimization(
        "int f(int x) { int t1 = x + 0; int t2 = t1 * 1; int t3 = t2 + t2; return t3; }",
        MockOptimizationGenerator(),
        3,
    )
    d = report.to_dict()
    assert d["summary"]["total_candidates"] == 3
    assert d["summary"]["accepted"] >= 1
