"""AST node definitions for the small source language.

The grammar (see docs/ir.md for the full write-up):

    program    := function+
    function   := "fn" IDENT "(" params? ")" "{" stmt* "}"
    params     := IDENT ("," IDENT)*
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
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Union


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
    """cond ? then_expr : else_expr -- the language's only branching construct."""
    cond: "Expr"
    then_expr: "Expr"
    else_expr: "Expr"


Expr = Union[NumberLit, VarRef, BinOp, UnaryOp, Conditional]


@dataclass(frozen=True)
class Assignment:
    name: str
    value: Expr


@dataclass(frozen=True)
class Return:
    value: Expr


Stmt = Union[Assignment, Return]


@dataclass(frozen=True)
class Function:
    name: str
    params: List[str]
    body: List[Stmt]


@dataclass(frozen=True)
class Program:
    functions: List[Function]
