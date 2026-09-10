# IR Design

## Source language

A tiny, brace-delimited expression language over mathematical integers:

```
fn compute(x, y) {
    a = x * 2;
    b = y + 0;
    c = a + a;
    return c + b;
}
```

Grammar (`backend/app/compiler/ast.py`):

```
program    := function+
function   := "fn" IDENT "(" params? ")" "{" stmt* "}"
stmt       := assign_stmt | return_stmt
assign_stmt:= IDENT "=" expr ";"
return_stmt:= "return" expr ";"
expr       := ternary
ternary    := comparison ("?" expr ":" expr)?
comparison := additive (("==" | "!=" | "<" | "<=" | ">" | ">=") additive)?
additive   := term (("+" | "-") term)*
term       := unary (("*" | "/" | "%") unary)*
unary      := "-" unary | primary
primary    := NUMBER | IDENT | "(" expr ")"
```

The only branching construct is the ternary `cond ? a : b`, which lowers
directly to the `SELECT` IR instruction -- there is no statement-level
`if`/`else`, no loops, no blocks-within-blocks. That keeps every program's
control-flow graph trivial (a straight line) so the whole function can be
encoded as a single Z3 expression with no path explosion.

## IR instruction set

Defined in `backend/app/compiler/ir.py`:

| Op | Fields | Meaning |
|---|---|---|
| `CONST` | dest, value | dest := literal integer |
| `ADD` / `SUB` / `MUL` / `DIV` / `MOD` | dest, lhs, rhs | dest := lhs OP rhs |
| `CMP` | dest, cmp, lhs, rhs | dest := (lhs cmp rhs), boolean-typed |
| `SELECT` | dest, cond, then, else | dest := cond ? then : else |
| `RETURN` | value | ends the function |

An operand (`lhs`, `rhs`, `cond`, `then`, `else`, `value`) is either a
JSON string (a reference to a parameter or an earlier temp) or a JSON
int (a literal). Every `dest` must be unique (true SSA) and every
reference must point to something already defined -- enforced by
`validate_ir()`, which runs on every IR function from any source
(compiled from source, or produced by an LLM/mock candidate).

## Example

```json
{
  "name": "compute",
  "params": ["x", "y"],
  "instructions": [
    {"op": "MUL", "dest": "t1", "lhs": "x", "rhs": 2},
    {"op": "ADD", "dest": "t2", "lhs": "y", "rhs": 0},
    {"op": "ADD", "dest": "t3", "lhs": "t1", "rhs": "t1"},
    {"op": "ADD", "dest": "t4", "lhs": "t3", "rhs": "t2"},
    {"op": "RETURN", "value": "t4"}
  ]
}
```

## Typing

There are exactly two "sorts": Int (everything by default) and Bool
(only the `dest` of a `CMP`). `SELECT.cond` must reference a `CMP`
result; `RETURN.value` must be Int-typed. This is checked structurally
during validation, not by a separate type-checker pass -- deliberately
minimal for a two-sort language.

## Division semantics

`DIV`/`MOD` use SMT-LIB/Z3's Euclidean semantics: for `b != 0` there is
a unique `q, r` with `a = b*q + r` and `0 <= r < |b|`. Division by zero
is a known limitation -- see the README's Limitations section.

## Why this restriction?

Formal equivalence checking is only tractable if the whole state space
is representable in a decidable theory. Mathematical (unbounded) integer
linear/nonlinear arithmetic over straight-line code is squarely inside
what Z3's arithmetic theories can decide quickly. Adding pointers, arrays,
loops, or fixed-width overflow semantics each independently make the
problem much harder (see docs/verification.md's Limitations and
FUTURE_WORK in the README).
