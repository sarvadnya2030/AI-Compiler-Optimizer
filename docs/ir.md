# IR Design

## Source language: mini-C

A tiny, real subset of C syntax over mathematical integers: typed
declarations, brace-delimited blocks, and genuine block-structured
`if`/`else` (including early returns and `else if` chains) -- restricted
to what stays formally verifiable (see "Why this restriction?" below).

```c
int compute(int x, int y) {
    int a = x * 2;
    int b = y + 0;
    int c = a + a;
    return c + b;
}
```

```c
int abs_val(int x) {
    if (x < 0) {
        return 0 - x;
    }
    return x;
}
```

Grammar (`backend/app/compiler/ast.py`):

```
program     := function+
function    := "int" IDENT "(" params? ")" "{" stmt* "}"
params      := "int" IDENT ("," "int" IDENT)*
stmt        := decl_stmt | assign_stmt | if_stmt | return_stmt
decl_stmt   := "int" IDENT "=" expr ";"
assign_stmt := IDENT "=" expr ";"
if_stmt     := "if" "(" expr ")" block ("else" (block | if_stmt))?
block       := "{" stmt* "}"
return_stmt := "return" expr ";"
expr        := ternary
ternary     := comparison ("?" expr ":" expr)?
comparison  := additive (("==" | "!=" | "<" | "<=" | ">" | ">=") additive)?
additive    := term (("+" | "-") term)*
term        := unary (("*" | "/" | "%") unary)*
unary       := "-" unary | primary
primary     := NUMBER | IDENT | "(" expr ")"
```

`int` is the only type (mathematical, unbounded -- not a real 32/64-bit
`int`). A variable must be declared (`int name = ...;`) before it can be
reassigned (`name = ...;`); the lowering pass rejects both redeclaration
and assignment to an undeclared name. There are no loops, pointers,
arrays, or structs -- see "Why this restriction?" below.

### Lowering block if/else: tail duplication

The IR itself has no branches, only a flat instruction list plus
`SELECT` (a ternary). Statement-level `if`/`else` is lowered by **tail
duplication**: everything that comes *after* an `if`/`else` in the same
block is appended onto *both* branches before recursing, and the two
branches' final return values are combined with one `SELECT` keyed on
the condition. Since the IR has no side effects, computing both branches
unconditionally is semantics-preserving -- it's exactly how the ternary
already worked, generalized from expressions to whole blocks. A branch
that already returns on every path (e.g. an early `return` inside an
`if` with no `else`) is *not* given the tail -- that would make it dead
code -- so:

```c
int abs_val(int x) {
    if (x < 0) { return 0 - x; }
    return x;
}
```

lowers to exactly:

```
CMP    t1 = lt x, 0
SUB    t2 = 0 - x
SELECT t3 = t1 ? t2 : x
RETURN t3
```

The cost of tail duplication is that instruction count can grow with
`if` nesting depth (each nested if-with-fallthrough duplicates
everything after it into both arms) -- acceptable for small, loop-free
mini-C programs; see `backend/app/compiler/lowering.py` for the full
algorithm and `docs/learning_roadmap.md` for a walkthrough.

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
