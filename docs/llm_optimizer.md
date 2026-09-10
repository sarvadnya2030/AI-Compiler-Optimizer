# LLM Optimizer

## Abstraction

```python
class OptimizationGenerator(ABC):
    def generate_candidates(self, program_ir: IRFunction, num_candidates: int) -> list[str]:
        """Return raw-text (JSON) candidates."""
```

Two implementations (`backend/app/optimizer/llm_optimizer.py`):

- `MockOptimizationGenerator` -- fully offline, deterministic. Returns the
  identity program, a peephole-simplified program (`optimizer/simplify.py`:
  constant folding, `x+0`/`x*1`/`x*0` identities, CSE, `x+x -> 2*x`), and
  a rotating set of intentionally-wrong mutations (flips `ADD`↔`MUL`,
  bumps a literal by 1, or replaces the return value). This is what makes
  the entire ACCEPT/REJECT pipeline demonstrable with zero external
  dependencies.
- `OllamaOptimizationGenerator` -- calls a local Ollama server's
  `/api/chat` HTTP endpoint with `format: "json"`, model configurable via
  `.env` (`OLLAMA_BASE_URL`, `OLLAMA_MODEL`).

Both return **raw text**. Nothing downstream trusts that text until
`candidate_parser.parse_candidate()` has JSON-decoded it and
`ir.from_dict()` has validated every field against the IR whitelist.

## Prompt construction

`backend/app/optimizer/prompt_builder.py` builds a prompt containing:

- the original program's IR as JSON
- the exact list of supported ops (`CONST, ADD, SUB, MUL, DIV, MOD, CMP, SELECT, RETURN`)
- the optimization objective (default: minimize instruction count)
- an explicit statement that a verifier will independently check the answer
- a worked schema example
- an instruction to return only JSON, no prose, no markdown fences

## Why the LLM is untrusted

An LLM can hallucinate a transformation that "looks like" a valid
optimization pattern (e.g. mistaking `x * x` for `2 * x`) with full
confidence and fluent-sounding output. Nothing about how confidently or
plausibly an LLM writes its answer bears any relation to whether the
answer is actually correct. This system's only correctness gate is the
Z3 equivalence check; the LLM/mock generator is purely a *source of
candidates*, structurally incapable of causing an incorrect optimization
to be accepted, because acceptance is computed from `VerificationStatus
== EQUIVALENT`, never from anything the generator says about itself.

## Security boundary

LLM (or mock) output is treated as untrusted input end-to-end:

- never `eval()`'d, never executed as code, never shelled out
- parsed only as JSON data
- every instruction shape and operand type is checked against the IR
  whitelist in `app/compiler/ir.py` before it ever reaches the Z3 encoder
- malformed candidates are reported as parse failures, not silently
  dropped or treated as equivalent
