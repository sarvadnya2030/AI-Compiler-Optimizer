"""AST node definitions for the mini-C source language.

The grammar (see docs/ir.md for the full write-up):

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

Only `int` (mathematical, unbounded) exists as a type -- there is no
type-checking pass beyond that single type, so the AST doesn't bother
carrying type annotations around; the parser just requires the `int`
keyword at every declaration site to make the surface syntax real C.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Union


@dataclass(frozen=True)
class NumberLit:
    value: int


@dataclass(frozen=True)
class VarRef:
    name: str


@dataclass(frozen=True)
class BinOp:
    op: str  # '+', '-', '*', '/', '%', '==', '!=', '<', '<=', '>', '>='
    left: "Expr"
    right: "Expr"


@dataclass(frozen=True)
class UnaryOp:
    op: str  # '-'
    operand: "Expr"


@dataclass(frozen=True)
class Conditional:
    """cond ? then_expr : else_expr -- an expression-level shorthand for If."""
    cond: "Expr"
    then_expr: "Expr"
    else_expr: "Expr"


Expr = Union[NumberLit, VarRef, BinOp, UnaryOp, Conditional]


@dataclass(frozen=True)
class VarDecl:
    """int name = value; -- introduces a new variable."""
    name: str
    value: Expr


@dataclass(frozen=True)
class Assign:
    """name = value; -- reassigns an already-declared variable/parameter."""
    name: str
    value: Expr


@dataclass(frozen=True)
class If:
    cond: Expr
    then_body: List["Stmt"]
    else_body: Optional[List["Stmt"]]  # None means no else clause


@dataclass(frozen=True)
class Return:
    value: Expr


Stmt = Union[VarDecl, Assign, If, Return]


@dataclass(frozen=True)
class Function:
    name: str
    params: List[str]
    body: List[Stmt]


@dataclass(frozen=True)
class Program:
    functions: List[Function]
