import pytest

from app.compiler.lexer import LexError, tokenize
from app.compiler.parser import ParseError, parse_function, parse_program


def test_parses_simple_function():
    fn = parse_function("int f(int x) { return x; }")
    assert fn.name == "f"
    assert fn.params == ["x"]
    assert len(fn.body) == 1


def test_parses_multiple_statements_and_ops():
    src = """
    int compute(int x, int y) {
        int a = x * 2;
        int b = y + 0;
        int c = a + a;
        return c + b;
    }
    """
    fn = parse_function(src)
    assert fn.params == ["x", "y"]
    assert len(fn.body) == 4


def test_parses_ternary_and_comparisons():
    fn = parse_function("int maxi(int x, int y) { return x > y ? x : y; }")
    assert len(fn.body) == 1


def test_parses_if_else_block():
    fn = parse_function("int maxi(int x, int y) { if (x > y) { return x; } else { return y; } }")
    assert len(fn.body) == 1


def test_parses_if_without_else_with_fallthrough():
    fn = parse_function("int abs_val(int x) { if (x < 0) { return 0 - x; } return x; }")
    assert len(fn.body) == 2


def test_parses_else_if_chain():
    src = """
    int sign(int x) {
        if (x > 0) { return 1; }
        else if (x < 0) { return 0 - 1; }
        else { return 0; }
    }
    """
    fn = parse_function(src)
    assert len(fn.body) == 1


def test_parses_multiple_functions():
    program = parse_program("int a(int x) { return x; } int b(int y) { return y + 1; }")
    assert len(program.functions) == 2
    assert [f.name for f in program.functions] == ["a", "b"]


def test_rejects_missing_semicolon():
    with pytest.raises(ParseError):
        parse_function("int f(int x) { return x }")


def test_rejects_missing_return():
    with pytest.raises(ParseError):
        parse_function("int f(int x) { int a = x + 1; }")


def test_rejects_if_without_terminal_branch_as_last_statement():
    with pytest.raises(ParseError):
        parse_function("int f(int x) { if (x > 0) { return 1; } }")


def test_rejects_unbalanced_parens():
    with pytest.raises(ParseError):
        parse_function("int f(int x) { return (x + 1; }")


def test_rejects_missing_type_keyword():
    with pytest.raises(ParseError):
        parse_function("int f(x) { return x; }")


def test_lexer_rejects_unknown_character():
    with pytest.raises(LexError):
        tokenize("int f(int x) { return x @ 1; }")


def test_parses_negative_numbers_and_unary_minus():
    fn = parse_function("int f(int x) { return -x + -1; }")
    assert len(fn.body) == 1


def test_parses_nested_parens():
    fn = parse_function("int f(int x, int y) { return (x + y) * (x - y); }")
    assert len(fn.body) == 1


def test_parses_modulo_and_division():
    fn = parse_function("int f(int x, int y) { int a = x / y; int b = x % y; return a + b; }")
    assert len(fn.body) == 3
