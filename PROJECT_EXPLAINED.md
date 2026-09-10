# AI Compiler Optimizer — Project Explained

A single, self-contained walkthrough of what this project is, how it
works, and why it's built the way it is. (The README covers setup/run
commands; `docs/` covers each subsystem in depth; this file is the
narrative that ties it all together.)

---

## 1. The idea in one sentence

An LLM proposes a "smarter" version of a small program; a Z3-based
formal verifier independently proves whether that version computes
*exactly* the same thing as the original for every possible input; only
proven-equivalent versions are ever accepted.

```
LLM proposes  →  Z3 formally proves/rejects  →  Optimizer selects
```

The LLM's opinion of its own answer never matters. Acceptance is a pure
function of what Z3 returns.

## 2. Why this needed building at all

Real compilers apply optimizations (constant folding, algebraic
simplification, common-subexpression elimination, strength reduction...)
that are supposed to leave a program's behavior unchanged while making
it cheaper to run. Traditionally, each optimization pass is written by a
compiler engineer and proven correct once, by hand, for all cases it
might touch.

LLMs are good at *proposing* these kinds of rewrites — often more
creatively and generally than a fixed set of hand-written peephole rules
— but an LLM has no actual guarantee attached to its output. It can say
`x * x → 2 * x` with exactly the same fluent confidence it says
`x + 0 → x`. One of those is correct for every integer; the other is
correct only at `x = 0` and `x = 2`. Nothing in *how* an LLM phrases an
answer tells you which situation you're in.

So the system is built around one hard rule: **the LLM only ever
proposes; a formal solver always decides.**

## 3. What "formal verification" means here, concretely

Given the original program and a candidate, both get turned into
symbolic math expressions over free integer variables (one per
parameter). The question "are these two programs equivalent?" becomes
one query to the Z3 SMT solver:

```python
solver.add(original_expr != optimized_expr)
result = solver.check()
```

- If Z3 says **UNSAT**, it just proved that no input exists where the
  two expressions differ — i.e., they're equal for *every* integer
  input. That's a real mathematical proof, not a test on a handful of
  sample inputs.
- If Z3 says **SAT**, it found an actual input where they disagree, and
  hands back that exact input as a *counterexample* — e.g. "at `x = 3`,
  original returns 9, candidate returns 6."
- If Z3 says **UNKNOWN** (solver timeout), the system reports `UNKNOWN`
  explicitly — it is never silently treated as equivalent.

This is the entire trust boundary of the project. Everything upstream
(parsing, the LLM, the mock generator) only ever produces *candidates*;
this one query is what turns a candidate into an accepted optimization.

## 4. The restricted language and why it exists

Formally verifying arbitrary C/C++ is not tractable for a project like
this (pointers, aliasing, undefined behavior, fixed-width overflow, and
loops each blow up the problem independently). So the system defines its
own small, from-scratch language over **mathematical (unbounded)
integers**:

```
fn compute(x, y) {
    a = x * 2;
    b = y + 0;
    c = a + a;
    return c + b;
}
```

Supported: integer variables/constants, `+ - * / %`, comparisons, a
ternary `cond ? a : b` (the only branching construct), and `return`.
Explicitly not supported (documented, not accidental): pointers, arrays,
structs, I/O, function calls, loops, concurrency, floating point. This
keeps every program a straight-line sequence of instructions with no
loops to reason about — which is exactly what lets the whole function be
encoded as a single Z3 expression, no path explosion, no invariants to
guess.

Source compiles down through a lexer → parser → AST → into an explicit,
SSA-style intermediate representation (IR) — every computed value gets
its own permanent name (`t1`, `t2`, ...), assigned exactly once:

```json
{
  "instructions": [
    {"op": "MUL", "dest": "t1", "lhs": "x", "rhs": 2},
    {"op": "ADD", "dest": "t2", "lhs": "t1", "rhs": "t1"},
    {"op": "RETURN", "value": "t2"}
  ]
}
```

The IR instruction set is deliberately tiny: `CONST, ADD, SUB, MUL, DIV,
MOD, CMP, SELECT, RETURN`. This same JSON shape is what the LLM is asked
to produce for its "optimized" answer — which sets up the next point.

## 5. Why LLM output is treated as hostile input, not just "unverified"

Whatever an LLM (or the mock generator standing in for one) returns is
raw text. Before it is ever compared to anything, it goes through:

1. JSON parsing (fenced code blocks stripped first, since models often
   wrap answers in ` ```json ` blocks) — malformed text is rejected here,
   not passed through.
2. A whitelist validator (`app/compiler/ir.py: validate_ir`) that checks
   every instruction is one of the 9 known ops, every field has the
   right type, every referenced name was actually defined earlier, every
   `dest` is unique, and the function ends in `RETURN`.
3. Only *then* does it become an `IRFunction` that the Z3 encoder is
   allowed to touch.

Nothing from an LLM is ever `eval()`'d, executed, or shelled out. A
candidate that fails step 1 or 2 is reported as a parse failure — never
silently dropped, never treated as equivalent by default.

## 6. Two candidate generators, same interface

```python
class OptimizationGenerator(ABC):
    def generate_candidates(self, program_ir, num_candidates) -> list[str]: ...
```

- **Mock (offline, deterministic)** — produces the identity program, a
  genuinely-correct peephole-simplified version (constant folding,
  `x+0`/`x*1`/`x*0` identities, common-subexpression elimination,
  `x+x → 2*x`), and a rotating set of *intentionally wrong* mutations
  (flip `ADD`↔`MUL`, bump a constant, or swap the return value). This
  means the whole ACCEPT/REJECT pipeline is demoable with **zero
  external dependencies** — no model, no network, no API key.
- **Ollama** — sends the IR + supported ops + objective to a local
  Ollama model over HTTP, asking for strict JSON back. Same untrusted
  treatment applies: whatever comes back goes through the identical
  parse-and-validate gate before it's compared to anything.

This was tested against a real local model (`qwen3:0.6b`) during
development, not just the mock — and it's a good illustration of the
whole point of the project: the model proposed two plausible-looking
rewrites, and Z3 caught both as wrong, complete with counterexamples
(e.g. at `x=0, y=0`, one rewrite produced `2` instead of the correct
`0`). A stronger model would presumably do better, but the system's
correctness never depends on that — it depends on Z3.

## 7. What the API/UI actually show you

`POST /api/optimize` runs the whole pipeline (compile source → generate
N candidates → parse+verify each → compute metrics) and returns, per
candidate: the candidate's IR, `EQUIVALENT` / `NOT_EQUIVALENT` /
`UNKNOWN` / `SIGNATURE_MISMATCH`, the real Z3 result (`unsat`/`sat`/
`unknown`), the actual measured verification time, a counterexample when
one exists, and (only for accepted candidates) instruction-count
reduction. The React dashboard renders this as one card per candidate,
green border + "ACCEPTED" for equivalent ones, red + counterexample for
rejected ones.

Example of a real run against this repo's own backend:

```
Original: t1 = x + 0; t2 = t1 * 1; t3 = t2 + t2; return t3 + y;

Candidate #2 (simplified): t3 = mul x, 2; t4 = add t3, y; return t4
  -> EQUIVALENT, Z3: unsat, 0.7ms, 40% instruction reduction

Candidate #3 (mutated ADD->MUL): 
  -> NOT_EQUIVALENT, Z3: sat, counterexample x=1, y=0: original=2, optimized=0
```

## 8. How "correctness" is kept honest, not just claimed

- Z3 is actually invoked on every single request — there is no
  hard-coded "assume equivalent" path anywhere in the code.
- Verification time is real `time.perf_counter()` wall-clock time around
  the actual solver call, not a fabricated number.
- The 40-program benchmark suite (`benchmarks/*.jsonl`, across
  arithmetic / algebraic / constant-folding / redundant-computation /
  control-flow categories) has each program paired with a specific
  candidate and a `candidate_equivalent` ground-truth flag — and a test
  (`backend/tests/test_benchmarks.py`) re-derives that flag from a live
  Z3 call on every test run, so the suite can never silently drift out
  of sync with what the verifier actually decides. All 40 currently
  match.
- 50 automated tests cover the parser, IR validation, Z3 encoding,
  equivalence checking, the mock optimizer, the benchmark suite, and the
  FastAPI routes — all passing.

## 9. The experiment framework (the "research" part)

`experiments/run_experiment.py` runs every benchmark program through a
chosen generator, verifies every candidate, and writes per-candidate
JSON/CSV records plus aggregate metrics: acceptance rate, rejection
rate, average verification latency, average instruction reduction. A
real run against the mock generator over all 40 benchmarks (3 candidates
each, 120 total):

```
accepted: 82/120 (68.33%)
avg verification latency: ~1.3ms
avg instruction reduction (accepted only): 10.67%
```

`experiments/analyze_results.py` compares multiple such runs side by
side — meant for comparing different LLMs/models against each other
using the same benchmark suite and the same pass/fail definition.

## 10. Known, documented limitations (not oversights)

- **No alpha-equivalence.** A candidate that renames a parameter (`x` →
  `z`) is reported as `SIGNATURE_MISMATCH`, not proven equivalent — the
  verifier compares functions over literally-named free variables and
  doesn't search over renamings.
- **Division by zero is underspecified**, per Z3's own SMT-LIB
  convention (a fixed-but-arbitrary value per model), not modeled after
  any particular real language's trap/exception behavior.
- **Instruction-count reduction is an IR-level proxy, not real
  speedup** — no native code is generated or benchmarked in this MVP.
- **The mock generator is not a model of real LLM failure modes** — it's
  a deterministic stand-in good enough to exercise and demo the
  ACCEPT/REJECT pipeline without external dependencies.

## 11. What's deliberately not built (and why it's hard)

Documented but out of scope for this MVP: LLVM IR integration, a real C
frontend, fixed-width (32-bit) integer semantics, loops (need invariants
or induction reasoning, not just straight-line encoding), memory/pointer
aliasing, floating point (a different, harder Z3 theory), Alive2-style
integration, native-code benchmarking, RL-based optimization selection,
LLM fine-tuning on accepted/rejected candidates, beam search over
candidates, and machine-checkable proof certificates (vs. "Z3 said
unsat, trust the solver").

## 12. Where things live (map, not exhaustive)

```
backend/app/compiler/   lexer, parser, AST, IR, AST->IR lowering
backend/app/optimizer/  mock + Ollama generators, candidate parsing,
                        peephole simplifier, accept/reject decision
backend/app/verifier/   Z3 encoder, equivalence checker, counterexamples
backend/app/metrics/    IR-level instruction-count metrics
backend/app/api/        FastAPI routes wiring it all together
frontend/src/           React dashboard (editor, config, candidate cards)
benchmarks/*.jsonl      40 programs, ground-truth-checked against Z3
experiments/            batch runner + cross-run comparison
docs/                   one deep-dive file per subsystem + a full
                        learning roadmap (docs/learning_roadmap.md)
```

For line-by-line teaching (compiler basics → this IR → Z3/SMT →
equivalence checking → the LLM optimizer → FastAPI → React → research
evaluation), read `docs/learning_roadmap.md` next.
