"""Lexer for the small IR source language.

Turns source text into a flat list of Tokens. The language is
brace-delimited (not indentation-sensitive) to keep the parser simple:

    fn compute(x, y) {
        a = x * 2;
        b = y + 0;
        return a + b;
    }
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    NUMBER = auto()
    IDENT = auto()
    FN = auto()
    RETURN = auto()
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    PERCENT = auto()
    ASSIGN = auto()
    EQ = auto()
    NEQ = auto()
    LT = auto()
    LTE = auto()
    GT = auto()
    GTE = auto()
    QUESTION = auto()
    COLON = auto()
    SEMI = auto()
    COMMA = auto()
    LPAREN = auto()
    RPAREN = auto()
    LBRACE = auto()
    RBRACE = auto()
    EOF = auto()


KEYWORDS = {"fn": TokenType.FN, "return": TokenType.RETURN}


@dataclass(frozen=True)
class Token:
    type: TokenType
    value: str
    line: int
    col: int


class LexError(Exception):
    def __init__(self, message: str, line: int, col: int):
        super().__init__(f"Lex error at {line}:{col}: {message}")
        self.line = line
        self.col = col


_SINGLE_CHAR = {
    "+": TokenType.PLUS,
    "-": TokenType.MINUS,
    "*": TokenType.STAR,
    "/": TokenType.SLASH,
    "%": TokenType.PERCENT,
    ";": TokenType.SEMI,
    ",": TokenType.COMMA,
    "(": TokenType.LPAREN,
    ")": TokenType.RPAREN,
    "{": TokenType.LBRACE,
    "}": TokenType.RBRACE,
    "?": TokenType.QUESTION,
    ":": TokenType.COLON,
}


def tokenize(source: str) -> list[Token]:
    tokens: list[Token] = []
    i = 0
    line = 1
    col = 1
    n = len(source)

    def advance(k: int = 1) -> None:
        nonlocal i, line, col
        for _ in range(k):
            if i < n and source[i] == "\n":
                line += 1
                col = 1
            else:
                col += 1
            i += 1

    while i < n:
        ch = source[i]

        if ch in " \t\r\n":
            advance()
            continue

        if ch == "#":
            while i < n and source[i] != "\n":
                advance()
            continue

        start_line, start_col = line, col

        if ch.isdigit():
            j = i
            while j < n and source[j].isdigit():
                j += 1
            value = source[i:j]
            advance(j - i)
            tokens.append(Token(TokenType.NUMBER, value, start_line, start_col))
            continue

        if ch.isalpha() or ch == "_":
            j = i
            while j < n and (source[j].isalnum() or source[j] == "_"):
                j += 1
            value = source[i:j]
            advance(j - i)
            ttype = KEYWORDS.get(value, TokenType.IDENT)
            tokens.append(Token(ttype, value, start_line, start_col))
            continue

        if ch == "=" and i + 1 < n and source[i + 1] == "=":
            advance(2)
            tokens.append(Token(TokenType.EQ, "==", start_line, start_col))
            continue
        if ch == "!" and i + 1 < n and source[i + 1] == "=":
            advance(2)
            tokens.append(Token(TokenType.NEQ, "!=", start_line, start_col))
            continue
        if ch == "<" and i + 1 < n and source[i + 1] == "=":
            advance(2)
            tokens.append(Token(TokenType.LTE, "<=", start_line, start_col))
            continue
        if ch == ">" and i + 1 < n and source[i + 1] == "=":
            advance(2)
            tokens.append(Token(TokenType.GTE, ">=", start_line, start_col))
            continue
        if ch == "=":
            advance()
            tokens.append(Token(TokenType.ASSIGN, "=", start_line, start_col))
            continue
        if ch == "<":
            advance()
            tokens.append(Token(TokenType.LT, "<", start_line, start_col))
            continue
        if ch == ">":
            advance()
            tokens.append(Token(TokenType.GT, ">", start_line, start_col))
            continue

        if ch in _SINGLE_CHAR:
            advance()
            tokens.append(Token(_SINGLE_CHAR[ch], ch, start_line, start_col))
            continue

        raise LexError(f"unexpected character {ch!r}", start_line, start_col)

    tokens.append(Token(TokenType.EOF, "", line, col))
    return tokens
