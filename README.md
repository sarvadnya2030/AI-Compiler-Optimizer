# AI Compiler Optimizer

**LLM-Generated Optimizations with Formal Equivalence Verification**

An AI-assisted compiler optimization system where an LLM (or a
deterministic offline mock) proposes optimized versions of a program,
and a Z3-based formal verifier independently proves — or disproves, with
a concrete counterexample — that each candidate is semantically
equivalent to the original. **The LLM is never trusted for correctness.**
Only candidates Z3 proves equivalent are accepted.

> Originally scoped as a compiler-design course project; built as a
> small but genuinely working research-grade MVP rather than a slide deck.

```
LLM proposes  →  Z3 formally proves/rejects  →  Optimizer selects
```

---

## 1. Problem

Compilers apply optimizations that are supposed to preserve program
behavior while improving some cost metric. Traditionally, every
optimization pass is hand-proven correct once, by the compiler's
authors. LLMs can propose plausible-looking optimizations far more
flexibly than hand-written peephole rules — but an LLM's fluency and
confidence carry no correctness guarantee whatsoever.

## 2. Motivation

If an LLM could reliably write correct optimizations, we wouldn't need a
verifier. It can't (yet), and probably shouldn't be trusted to even if
it seemed to for a while. So: let the LLM be a fast, creative *proposer*
of transformations, and let a formal method be the *only* gate between
"proposed" and "shipped".

## 3. Architecture

```
Source Program → Parser/Frontend → IR → LLM Optimizer → Candidate Parser
   → Z3 Semantic Encoder → Equivalence Check → ACCEPT/REJECT → Metrics
```

See `docs/architecture.md` for the full diagram and module boundaries.

## 4. Why LLMs are useful

They can propose non-obvious algebraic rewrites, combine multiple
identities in one step, and generalize across many program shapes
without anyone hand-writing a rule for each one.

## 5. Why LLM output cannot be trusted

An LLM can output `x * x → 2 * x` with exactly the same fluency and
confidence as `x + 0 → x`. One is correct, one is not, and nothing about
*how* the answer was produced tells you which is which. See
`docs/llm_optimizer.md`.

## 6. Why formal verification is needed

Testing on sample inputs can miss the one input where a transformation
breaks. Z3 checks *all* integer inputs at once via a solver query — see
`docs/verification.md`.

## 7. How Z3 works / 8. Equivalence checking / 9. IR design

Covered in depth in `docs/verification.md`, `docs/ir.md`, and the full
teaching write-up in `docs/learning_roadmap.md`.

## 10. Installation

```bash
git clone <this-repo>
cd ai-compiler-verifier
cp .env.example backend/.env
```

Backend:
```bash
python3.11 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
```

Frontend:
```bash
cd frontend && npm install
```

## 11. Running locally

One command (starts both, Ctrl+C stops both):
```bash
./scripts/dev.sh
```

Or separately:
```bash
./scripts/start_backend.sh    # http://localhost:8000
./scripts/start_frontend.sh   # http://localhost:5173
```

`MOCK_LLM=true` (the default in `.env.example`) means the whole pipeline
works with **zero external dependencies** — no Ollama, no API keys.

## 12. Running with Ollama

```bash
ollama serve
ollama pull qwen3:0.6b   # any Ollama model works; small ones are faster locally
```

In `backend/.env`:
```
LLM_BACKEND=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:0.6b
```

Or per-request, via the API's `llm_backend`/`ollama_model` fields, or the
UI's LLM dropdown.

## 13. Running tests

```bash
./scripts/run_tests.sh
```

47+ tests across parser, IR, Z3 encoding, equivalence checking, the
optimizer/mock generator, the benchmark suite (cross-checked live
against Z3), and the FastAPI routes.

## 14. Running experiments

```bash
python experiments/run_experiment.py --backend mock --num-candidates 3
python experiments/analyze_results.py experiments/results/*.json
```

Runs the pipeline over all `benchmarks/*.jsonl` programs and writes
per-candidate JSON + CSV results plus aggregate metrics (acceptance
rate, rejection rate, average verification latency, average instruction
reduction) to `experiments/results/`.

## 15. Limitations

- **Restricted language**: mathematical integers only — no fixed-width
  overflow, no pointers, arrays, structs, I/O, function calls, loops, or
  floating point. See `docs/ir.md` for why.
- **No alpha-equivalence**: a candidate that renames a parameter is
  reported as a signature mismatch, not proven equivalent.
- **Division by zero is underspecified** (Z3's SMT-LIB convention, not a
  real language's div-by-zero semantics). See `docs/verification.md`.
- **IR-level metrics only**: instruction-count reduction is not a proxy
  for real CPU speedup; no native code is generated or benchmarked.
- **Mock generator ≠ real LLM behavior**: it's a useful stand-in for
  demoing and testing the ACCEPT/REJECT pipeline, not a model of real
  LLM failure modes.

## 16. Future work

Documented, deliberately **not** implemented in this MVP (see the code
comments and `docs/` files for why each is hard):

LLVM IR integration · a real C frontend · 32-bit bit-vector semantics ·
loop handling (needs invariants/induction, not just straight-line
encoding) · memory modeling (aliasing) · floating point (Z3's FP theory
is a different beast) · Alive2 integration · standard compiler benchmark
suites · native-code benchmarking for real speedup numbers ·
reinforcement learning over optimization selection · LLM fine-tuning on
accepted/rejected candidates · beam search over candidates · multi-stage
(iterated) optimization · machine-checkable proof certificates instead
of "Z3 said unsat, trust us".

## Example API calls

**Health:**
```bash
curl http://localhost:8000/api/health
```

**Optimize (mock LLM):**
```bash
curl -X POST http://localhost:8000/api/optimize \
  -H "Content-Type: application/json" \
  -d '{"program": "fn f(x) { t1 = x + 0; t2 = t1 * 1; t3 = t2 + t2; return t3; }", "num_candidates": 4, "llm_backend": "mock"}'
```

**Verify a specific pair (accepted example):**
```bash
curl -X POST http://localhost:8000/api/verify \
  -H "Content-Type: application/json" \
  -d '{"original_program": "fn f(x) { return x + 0; }", "optimized_program": "fn f(x) { return x; }"}'
# -> {"verification": {"status": "EQUIVALENT", "z3_result": "unsat", "counterexample": null, ...}}
```

**Verify a specific pair (rejected example, with counterexample):**
```bash
curl -X POST http://localhost:8000/api/verify \
  -H "Content-Type: application/json" \
  -d '{"original_program": "fn f(x) { return x * x; }", "optimized_program": "fn f(x) { return 2 * x; }"}'
# -> {"verification": {"status": "NOT_EQUIVALENT", "z3_result": "sat",
#      "counterexample": {"inputs": {"x": -8}, "original_output": 64, "optimized_output": -16}, ...}}
```

## Most important files

| File | Why it matters |
|---|---|
| `backend/app/compiler/ir.py` | The whole IR + its validation (the whitelist untrusted candidates must pass) |
| `backend/app/verifier/z3_encoder.py` | Turns IR into Z3 symbolic expressions |
| `backend/app/verifier/equivalence.py` | The actual proof query and ACCEPT/REJECT mapping |
| `backend/app/optimizer/llm_optimizer.py` | Mock + Ollama candidate generators |
| `backend/app/optimizer/pipeline.py` | Wires the whole pipeline together end to end |
| `experiments/run_experiment.py` | Batch runner producing the research metrics |

## Repository structure

```
ai-compiler-verifier/
├── backend/app/{compiler,optimizer,verifier,metrics,api}/
├── backend/tests/
├── frontend/src/{components,pages,api}/
├── benchmarks/*.jsonl
├── experiments/{run_experiment.py,analyze_results.py,results/}
├── docs/{architecture,ir,verification,llm_optimizer,learning_roadmap}.md
└── scripts/{dev,start_backend,start_frontend,run_tests}.sh
```

## Learning roadmap

New to this codebase? Read `docs/learning_roadmap.md` — it teaches the
whole system in order: compiler basics → this IR → Z3/SMT → equivalence
checking → the LLM optimizer → FastAPI → the React frontend → how to
evaluate the research results.
