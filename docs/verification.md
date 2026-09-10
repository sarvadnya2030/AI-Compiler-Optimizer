# Formal Verification

## The query

For two IR functions sharing the same parameter set, equivalence is:

```
forall inputs: original(inputs) == optimized(inputs)
```

Z3 (and SMT solvers generally) prove universal statements by refutation:
instead of asking Z3 to prove the `forall`, we ask it to find a
counterexample to it:

```python
solver.add(original_output != optimized_output)
result = solver.check()
```

- `UNSAT` -- no input makes the two outputs differ -- the `forall` holds -- **EQUIVALENT**.
- `SAT` -- Z3 found a concrete input where they differ -- **NOT_EQUIVALENT**, and
  the model gives you a real counterexample for free.
- `UNKNOWN` -- the solver could not decide (e.g. it hit the timeout) -- **never**
  treated as equivalent; surfaced as its own status.

This mapping lives in `backend/app/verifier/equivalence.py`.

## Encoding

`backend/app/verifier/z3_encoder.py` walks an `IRFunction`'s instructions
once, in order, maintaining a `name -> z3 expression` environment:

- Each parameter becomes a free `z3.Int(name)`.
- `CONST` becomes `z3.IntVal(value)`.
- `ADD`/`SUB`/`MUL`/`DIV`/`MOD` become the corresponding Z3 operator.
- `CMP` becomes a Z3 `BoolRef` (`==`, `!=`, `<`, `<=`, `>`, `>=`).
- `SELECT` becomes `z3.If(cond, then, else)`.
- `RETURN`'s operand is the function's symbolic output expression.

Two functions that share parameter *names* automatically share the same
underlying Z3 symbols (`z3.Int("x")` called twice returns terms over the
same symbol), which is what lets the equivalence checker just diff their
two return expressions directly.

## Counterexamples

When `solver.check()` returns `SAT`, `solver.model()` gives a concrete
assignment. `EquivalenceChecker._build_counterexample` evaluates every
parameter and both return expressions under that model and packages them
into a `Counterexample(inputs, original_output, optimized_output)`
(`backend/app/verifier/counterexample.py`). Example:

```
Original:  x * x
Candidate: 2 * x

Counterexample: x = 3
Original output: 9
Optimized output: 6
```

## Never faked

- The Z3 solver is actually invoked on every request; there is no
  hard-coded "assume equivalent" path anywhere in the codebase.
- `verification_time_ms` is `time.perf_counter()` wall-clock time around
  the actual `solver.check()` call, not a fabricated number.
- A parameter-name mismatch between original and candidate short-circuits
  to `SIGNATURE_MISMATCH` *before* calling Z3, since the query would be
  meaningless (see the limitation below) -- this is the only status that
  doesn't come from a live solver call, and it is never mapped to accepted.

## Known limitations

- **Alpha-equivalence isn't recognized.** A candidate that renames `x` to
  `z` is reported as `SIGNATURE_MISMATCH`, not `EQUIVALENT`, even though
  it's semantically the same function. Fixing this would mean checking
  equivalence over all parameter permutations/renamings, which the MVP
  does not attempt.
- **Division by zero is underspecified.** Z3 treats `a/0` and `a%0` as a
  fixed-but-arbitrary value per model rather than raising anything. Two
  programs that both divide by a possibly-zero value are compared "as
  Z3 sees it", not against a real language's div-by-zero behavior (trap,
  exception, etc.) -- there is no real language semantics here since this
  is a from-scratch mathematical-integer IR.
- **UNKNOWN can happen** for `DIV`/`MOD`-heavy nonlinear queries if Z3's
  timeout (`Z3_TIMEOUT_MS`, default 5000ms) is hit; it is surfaced, not
  silently treated as anything else.
