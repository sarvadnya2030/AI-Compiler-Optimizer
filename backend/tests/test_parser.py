import pytest

from app.compiler.lexer import LexError, tokenize
from app.compiler.parser import ParseError, parse_function, parse_program


def test_parses_simple_function():
    fn = parse_function("fn f(x) { return x; }")
    assert fn.name == "f"
    assert fn.params == ["x"]
    assert len(fn.body) == 1


def test_parses_multiple_statements_and_ops():
    src = """
    fn compute(x, y) {
        a = x * 2;
        b = y + 0;
        c = a + a;
        return c + b;
    }
    """
    fn = parse_function(src)
    assert fn.params == ["x", "y"]
    assert len(fn.body) == 4


def test_parses_ternary_and_comparisons():
    fn = parse_function("fn maxi(x, y) { return x > y ? x : y; }")
    assert len(fn.body) == 1


def test_parses_multiple_functions():
    program = parse_program("fn a(x) { return x; } fn b(y) { return y + 1; }")
    assert len(program.functions) == 2
    assert [f.name for f in program.functions] == ["a", "b"]


def test_rejects_missing_semicolon():
    with pytest.raises(ParseError):
        parse_function("fn f(x) { return x }")


def test_rejects_missing_return():
    with pytest.raises(ParseError):
        parse_function("fn f(x) { a = x + 1; }")


def test_rejects_unbalanced_parens():
    with pytest.raises(ParseError):
        parse_function("fn f(x) { return (x + 1; }")


def test_lexer_rejects_unknown_character():
    with pytest.raises(LexError):
        tokenize("fn f(x) { return x @ 1; }")


def test_parses_negative_numbers_and_unary_minus():
    fn = parse_function("fn f(x) { return -x + -1; }")
    assert len(fn.body) == 1


def test_parses_nested_parens():
    fn = parse_function("fn f(x, y) { return (x + y) * (x - y); }")
    assert len(fn.body) == 1


def test_parses_modulo_and_division():
    fn = parse_function("fn f(x, y) { a = x / y; b = x % y; return a + b; }")
    assert len(fn.body) == 3
