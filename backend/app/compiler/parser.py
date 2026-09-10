"""Recursive-descent parser: tokens -> AST.

See ast.py for the grammar this implements.
"""
from __future__ import annotations

from .lexer import Token, TokenType, tokenize
from . import ast as A

_COMPARISON_OPS = {
    TokenType.EQ: "==",
    TokenType.NEQ: "!=",
    TokenType.LT: "<",
    TokenType.LTE: "<=",
    TokenType.GT: ">",
    TokenType.GTE: ">=",
}


class ParseError(Exception):
    def __init__(self, message: str, token: Token):
        super().__init__(f"Parse error at {token.line}:{token.col}: {message} (got {token.type.name!r})")
        self.token = token


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    # -- token stream helpers -------------------------------------------------
    def _peek(self) -> Token:
        return self.tokens[self.pos]

    def _advance(self) -> Token:
        tok = self.tokens[self.pos]
        if tok.type != TokenType.EOF:
            self.pos += 1
        return tok

    def _check(self, ttype: TokenType) -> bool:
        return self._peek().type == ttype

    def _expect(self, ttype: TokenType) -> Token:
        if not self._check(ttype):
            raise ParseError(f"expected {ttype.name}", self._peek())
        return self._advance()

    # -- grammar ---------------------------------------------------------------
    def parse_program(self) -> A.Program:
        functions = []
        while not self._check(TokenType.EOF):
            functions.append(self._parse_function())
        if not functions:
            raise ParseError("program must contain at least one function", self._peek())
        return A.Program(functions=functions)

    def _parse_function(self) -> A.Function:
        self._expect(TokenType.FN)
        name_tok = self._expect(TokenType.IDENT)
        self._expect(TokenType.LPAREN)
        params: list[str] = []
        if not self._check(TokenType.RPAREN):
            params.append(self._expect(TokenType.IDENT).value)
            while self._check(TokenType.COMMA):
                self._advance()
                params.append(self._expect(TokenType.IDENT).value)
        self._expect(TokenType.RPAREN)
        self._expect(TokenType.LBRACE)
        body: list[A.Stmt] = []
        while not self._check(TokenType.RBRACE):
            body.append(self._parse_stmt())
        self._expect(TokenType.RBRACE)
        if not body or not isinstance(body[-1], A.Return):
            raise ParseError("function body must end with a return statement", self._peek())
        return A.Function(name=name_tok.value, params=params, body=body)

    def _parse_stmt(self) -> A.Stmt:
        if self._check(TokenType.RETURN):
            self._advance()
            value = self._parse_expr()
            self._expect(TokenType.SEMI)
            return A.Return(value=value)

        name_tok = self._expect(TokenType.IDENT)
        self._expect(TokenType.ASSIGN)
        value = self._parse_expr()
        self._expect(TokenType.SEMI)
        return A.Assignment(name=name_tok.value, value=value)

    def _parse_expr(self) -> A.Expr:
        return self._parse_ternary()

    def _parse_ternary(self) -> A.Expr:
        cond = self._parse_comparison()
        if self._check(TokenType.QUESTION):
            self._advance()
            then_expr = self._parse_expr()
            self._expect(TokenType.COLON)
            else_expr = self._parse_expr()
            return A.Conditional(cond=cond, then_expr=then_expr, else_expr=else_expr)
        return cond

    def _parse_comparison(self) -> A.Expr:
        left = self._parse_additive()
        if self._peek().type in _COMPARISON_OPS:
            op = _COMPARISON_OPS[self._advance().type]
            right = self._parse_additive()
            return A.BinOp(op=op, left=left, right=right)
        return left

    def _parse_additive(self) -> A.Expr:
        left = self._parse_term()
        while self._peek().type in (TokenType.PLUS, TokenType.MINUS):
            op = "+" if self._advance().type == TokenType.PLUS else "-"
            right = self._parse_term()
            left = A.BinOp(op=op, left=left, right=right)
        return left

    _TERM_OPS = {TokenType.STAR: "*", TokenType.SLASH: "/", TokenType.PERCENT: "%"}

    def _parse_term(self) -> A.Expr:
        left = self._parse_unary()
        while self._peek().type in self._TERM_OPS:
            op = self._TERM_OPS[self._advance().type]
            right = self._parse_unary()
            left = A.BinOp(op=op, left=left, right=right)
        return left

    def _parse_unary(self) -> A.Expr:
        if self._check(TokenType.MINUS):
            self._advance()
            return A.UnaryOp(op="-", operand=self._parse_unary())
        return self._parse_primary()

    def _parse_primary(self) -> A.Expr:
        tok = self._peek()
        if tok.type == TokenType.NUMBER:
            self._advance()
            return A.NumberLit(value=int(tok.value))
        if tok.type == TokenType.IDENT:
            self._advance()
            return A.VarRef(name=tok.value)
        if tok.type == TokenType.LPAREN:
            self._advance()
            inner = self._parse_expr()
            self._expect(TokenType.RPAREN)
            return inner
        raise ParseError("expected an expression", tok)


def parse_program(source: str) -> A.Program:
    tokens = tokenize(source)
    return Parser(tokens).parse_program()


def parse_function(source: str) -> A.Function:
    """Convenience for the common single-function case."""
    program = parse_program(source)
    return program.functions[0]
