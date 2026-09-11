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

    def _peek_next(self) -> Token:
        return self.tokens[min(self.pos + 1, len(self.tokens) - 1)]

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
        self._expect(TokenType.INT)  # return type -- only `int` is supported
        name_tok = self._expect(TokenType.IDENT)
        self._expect(TokenType.LPAREN)
        params: list[str] = []
        if not self._check(TokenType.RPAREN):
            self._expect(TokenType.INT)
            params.append(self._expect(TokenType.IDENT).value)
            while self._check(TokenType.COMMA):
                self._advance()
                self._expect(TokenType.INT)
                params.append(self._expect(TokenType.IDENT).value)
        self._expect(TokenType.RPAREN)
        body = self._parse_block()
        if not body or not self._is_terminal(body[-1]):
            raise ParseError("every control path must end with a return statement", self._peek())
        return A.Function(name=name_tok.value, params=params, body=body)

    def _parse_block(self) -> list[A.Stmt]:
        self._expect(TokenType.LBRACE)
        stmts: list[A.Stmt] = []
        while not self._check(TokenType.RBRACE):
            stmts.append(self._parse_stmt())
        self._expect(TokenType.RBRACE)
        return stmts

    @staticmethod
    def _is_terminal(stmt: A.Stmt) -> bool:
        """A statement that guarantees its control path returns."""
        if isinstance(stmt, A.Return):
            return True
        if isinstance(stmt, A.If):
            return stmt.else_body is not None and bool(stmt.then_body) and bool(stmt.else_body) and Parser._is_terminal(
                stmt.then_body[-1]
            ) and Parser._is_terminal(stmt.else_body[-1])
        return False

    def _parse_stmt(self) -> A.Stmt:
        if self._check(TokenType.RETURN):
            self._advance()
            value = self._parse_expr()
            self._expect(TokenType.SEMI)
            return A.Return(value=value)

        if self._check(TokenType.INT):
            self._advance()
            name_tok = self._expect(TokenType.IDENT)
            self._expect(TokenType.ASSIGN)
            value = self._parse_expr()
            self._expect(TokenType.SEMI)
            return A.VarDecl(name=name_tok.value, value=value)

        if self._check(TokenType.IF):
            return self._parse_if()

        name_tok = self._expect(TokenType.IDENT)
        self._expect(TokenType.ASSIGN)
        value = self._parse_expr()
        self._expect(TokenType.SEMI)
        return A.Assign(name=name_tok.value, value=value)

    def _parse_if(self) -> A.If:
        self._expect(TokenType.IF)
        self._expect(TokenType.LPAREN)
        cond = self._parse_expr()
        self._expect(TokenType.RPAREN)
        then_body = self._parse_block()

        else_body = None
        if self._check(TokenType.ELSE):
            self._advance()
            if self._check(TokenType.IF):
                else_body = [self._parse_if()]
            else:
                else_body = self._parse_block()

        return A.If(cond=cond, then_body=then_body, else_body=else_body)

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
