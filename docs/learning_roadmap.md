# Learning Roadmap

Read this top to bottom the first time. Each section: **what it is**,
**why we need it**, **where it appears in our code**, **simple example**.

---

## Phase 1 — Compiler basics

**Lexer.** Turns raw text into a flat stream of tokens (numbers,
identifiers, keywords, punctuation). Why: the parser shouldn't have to
deal with whitespace, comments, or character-by-character scanning.
Where: `backend/app/compiler/lexer.py`. Example: `"x + 1"` becomes
`[IDENT(x), PLUS, NUMBER(1), EOF]`.

**Parser / AST.** Turns tokens into a tree that reflects the grammar's
structure (a *concrete* structure the language actually has, as opposed
to a flat token list). Why: `2 + 3 * 4` needs to know `*` binds tighter
than `+` — that's exactly what a tree encodes and a flat list doesn't.
Where: `backend/app/compiler/parser.py` builds nodes from
`backend/app/compiler/ast.py`. Example: `x * 2 + y` becomes
`BinOp(+, BinOp(*, VarRef(x), NumberLit(2)), VarRef(y))`.

**IR (Intermediate Representation).** A lower-level, more explicit form
than the AST — every intermediate value gets its own name. Why: it's
much easier to reason about, transform, and (in our case) translate to
Z3 than a nested tree of expressions. Where: `backend/app/compiler/ir.py`.

**SSA (Static Single Assignment).** A discipline where every variable is
assigned exactly once. Why: it removes ambiguity about "which write does
this read see" — critical when you're about to hand instructions to a
solver that has no notion of mutable state. Where: `lowering.py` assigns
a fresh `tN` name every time it needs a new value; `validate_ir()` in
`ir.py` enforces that no `dest` repeats.

**Optimization.** A transformation that produces a new program computing
the same result, ideally cheaper. Why it's the whole point of this
project: normally a compiler *trusts* its own optimization passes
(they're hand-proven once, by the compiler's authors). Here, the
"optimizer" is an LLM or a simple heuristic, neither of which we trust —
so every single transformation gets independently proven, every time.
Where: `backend/app/optimizer/`.

---

## Phase 2 — Our IR

Every class in `backend/app/compiler/ir.py`:

- `ConstInstr(dest, value)` — dest := a literal integer.
- `BinArithInstr(op, dest, lhs, rhs)` — op ∈ {ADD, SUB, MUL, DIV, MOD}.
- `CmpInstr(dest, cmp, lhs, rhs)` — cmp ∈ {eq, ne, lt, le, gt, ge}; the
  *only* boolean-typed instruction.
- `SelectInstr(dest, cond, then_val, else_val)` — a ternary; `cond` must
  reference a `CmpInstr`'s dest.
- `ReturnInstr(value)` — always the last instruction.

`IRFunction(name, params, instructions)` bundles these with a parameter
list. `to_dict`/`from_dict` are the JSON (de)serializers; `validate_ir`
is the single source of truth for "is this a legal IR program" — it's
run on IR compiled from source *and* on every candidate an LLM produces,
so there's exactly one place that decides IR legality.

The source language (mini-C) has real block `if`/`else`, but the IR
still has no branches at all — only `SelectInstr`. The frontend's
`lowering.py` bridges that gap with **tail duplication**: everything
after an `if`/`else` gets appended onto both branches before lowering
continues, so an early return collapses into one `SELECT` just like a
ternary would. Worked example in `docs/ir.md`.

See `docs/ir.md` for the full instruction table and grammar.

---

## Phase 3 — Z3 / SMT

**SMT (Satisfiability Modulo Theories).** A solver that decides whether a
logical formula is satisfiable, where the formula can talk about
specific *theories* (here: linear/nonlinear integer arithmetic), not
just raw boolean variables like a plain SAT solver.

**Symbolic variables.** `z3.Int("x")` doesn't hold one number — it
stands for *any* integer. Building an expression out of symbolic
variables (`x + x`) creates a symbolic formula, not a computed value.

**Constraints.** `solver.add(expr)` tells the solver "this must be true".
You can add many; the solver looks for one assignment to all symbolic
variables that satisfies all of them simultaneously.

**SAT vs UNSAT.** `solver.check()` returns `sat` if such an assignment
exists, `unsat` if it provably does not, `unknown` if the solver gave up.

**Models.** When `sat`, `solver.model()` gives you one concrete
assignment that satisfies everything — a witness.

**Counterexamples.** In our use, the constraint we add is "the two
programs disagree". A model for that constraint literally *is* a
counterexample: a concrete input where they actually do disagree.

Where: `backend/app/verifier/z3_encoder.py` (building the symbolic
expressions), `backend/app/verifier/equivalence.py` (adding the
constraint and interpreting the result).

---

## Phase 4 — Equivalence checking

The exact transformation from "are these two programs equal?" to a Z3
query, in `backend/app/verifier/equivalence.py`:

```python
original_enc = encoder.encode(original_ir)     # -> z3 expression A
optimized_enc = encoder.encode(optimized_ir)   # -> z3 expression B

solver = z3.Solver()
solver.add(original_enc.return_expr != optimized_enc.return_expr)
result = solver.check()
```

We never ask Z3 to prove `forall x: A(x) == B(x)` directly — instead we
ask "does a counterexample to that exist?" and flip the answer:
`unsat` on the negation means the original claim holds for *all* inputs.
This is the standard way SMT solvers are used for verification, and it's
why `UNSAT` maps to `EQUIVALENT`, not the other way around — it can feel
backwards the first time you see it.

Full walkthrough: `docs/verification.md`.

---

## Phase 5 — LLM optimization

**Prompt construction.** The prompt tells the model exactly which ops
exist, what the objective is, and demands JSON matching our IR schema —
narrowing the LLM's output space as much as possible before it ever
generates anything. Where: `backend/app/optimizer/prompt_builder.py`.

**Structured output.** We ask Ollama for `format: "json"` and still parse
defensively (strip code fences, catch `JSONDecodeError`) because models
don't always comply perfectly.

**Candidate generation.** `OptimizationGenerator.generate_candidates`
is the one interface both the mock and the real backend implement — the
rest of the system doesn't know or care which one produced a given
candidate.

**Why the LLM is untrusted.** See `docs/llm_optimizer.md` — in short,
fluent and confident output has zero correlation with actual semantic
correctness, so no amount of "this really looks right" ever substitutes
for an actual proof.

---

## Phase 6 — FastAPI

**Routes.** Each endpoint is a plain Python function decorated with
`@router.post(...)`/`@router.get(...)`, grouped by concern in
`backend/app/api/routes/`.

**Pydantic.** Request bodies are declared as `BaseModel` subclasses
(e.g. `OptimizeRequest` in `optimize.py`) — FastAPI validates incoming
JSON against them automatically and returns a 422 on mismatch, so route
functions never have to hand-check "did the client send a string here".

**Request/response lifecycle.** Client sends JSON → FastAPI validates
into a Pydantic model → route function runs (here: calls into
`optimizer/pipeline.py`) → the returned dict is serialized back to JSON.

**Sync, deliberately.** Z3 calls and mock generation are CPU-bound, not
I/O-bound, so the routes are plain `def`, not `async def` — `async` only
pays off for I/O-bound work (e.g. the real Ollama HTTP call uses
`requests`, which is blocking; a future improvement would make that path
async so many concurrent Ollama requests don't block each other, without
changing the CPU-bound Z3 path at all).

---

## Phase 7 — React frontend

The minimum you need: `frontend/src/pages/Dashboard.jsx` holds all UI
state (`program` text, `config`, the last `report`) using `useState`.
`ConfigPanel.jsx` and `CandidateCard.jsx` are pure "given props, render
this" components — no state of their own. `frontend/src/api/client.js`
is a thin `fetch()` wrapper around the four backend endpoints. Clicking
"Generate" calls `/api/optimize` and stores the JSON response directly
in state; React re-renders `CandidateCard` once per candidate in the
response.

---

## Phase 8 — Research evaluation

**Acceptance rate.** `accepted / total_candidates` — how often a given
generator's proposals actually survive formal verification. This is the
single most important number for comparing generators/models, because
it directly measures how often the generator's output can be trusted
*without* the verifier (spoiler: never — that's the whole point — but a
higher rate means less wasted generation).

**Verification latency.** Real wall-clock time per Z3 call. Matters
because a system that proves correctness but takes seconds per candidate
doesn't scale to being an actual compiler pass.

**Optimization effectiveness.** Instruction-count reduction, only ever
computed for *accepted* candidates (see `docs/architecture.md` for why
this is explicitly labeled IR-level, not real speedup).

**Benchmark methodology.** `benchmarks/*.jsonl` records pair a program
with a specific candidate and a `candidate_equivalent` ground-truth flag
that is cross-checked against a live Z3 run in
`backend/tests/test_benchmarks.py` — so the suite can never silently
drift out of sync with what the verifier actually decides.

**Threats to validity.** (1) The benchmark suite is hand-written by the
project author, so it reflects the author's intuition about interesting
cases, not a random sample of real optimizations. (2) The mock generator
is not a real LLM and may not represent real LLM failure modes. (3) IR
instruction count is a crude proxy for real-world performance (see
Limitations in the README).

Where to run this yourself: `experiments/run_experiment.py` and
`experiments/analyze_results.py`.
