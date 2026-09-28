from sympy import E, I, count_ops, pi, exp, sin, cos, symbols, simplify
from sympy.testing.pytest import raises  # noqa: F401 (documents test style)

from maxsymp import MaxSymp, sympy_to_maxima

x, y = symbols("x y")


def test_translation_keeps_user_symbols():
    pie, Inner = symbols("pie Inner")
    assert sympy_to_maxima(pie) == "pie"
    assert sympy_to_maxima(Inner) == "Inner"


def test_translation_constants():
    assert sympy_to_maxima(E) == "%e"
    assert sympy_to_maxima(pi) == "%pi"
    assert sympy_to_maxima(I) == "%i"


def test_rational_cancel():
    assert MaxSymp((x**2 - 1) / (x - 1)) == x + 1


def test_exp_combine():
    assert MaxSymp(exp(x) * exp(y)) == exp(x + y)


def test_trig_pythagoras():
    # Maxima trigsimp should reduce the Pythagorean identity to 1.
    e = sin(x) ** 2 + cos(x) ** 2
    assert MaxSymp(e) == 1


def test_roundtrip_pi():
    assert MaxSymp(pi) == pi


def test_sin3_over_sin1_maxima_only():
    # SymPy 1.12.1 leaves this untouched; Maxima trigrat resolves it.
    e = sin(3 * x) / sin(x)
    assert simplify(e) == e
    assert MaxSymp(e) == 2 * cos(2 * x) + 1


def test_cos3_over_cos1_maxima_only():
    e = cos(3 * x) / cos(x)
    assert simplify(e) == e
    assert MaxSymp(e) == 2 * cos(2 * x) - 1


def test_sin5_over_sin1_maxima_only():
    e = sin(5 * x) / sin(x)
    assert simplify(e) == e
    assert MaxSymp(e) == 2 * cos(4 * x) + 2 * cos(2 * x) + 1


def test_default_pipeline_expands_square():
    # Default (no complexity hook) uses the aggressive trigrat chain, which expands.
    assert MaxSymp((x + 1) ** 2) == x**2 + 2 * x + 1


def test_complexity_count_ops_prefers_factored():
    # factor((x+1)^2) stays compact; ratsimp expands it. count_ops picks factored.
    assert MaxSymp((x + 1) ** 2, complexity=count_ops) == (x + 1) ** 2


def test_complexity_can_prefer_expanded():
    # Negated cost prefers the larger (expanded) form instead.
    assert MaxSymp((x + 1) ** 2, complexity=lambda e: -count_ops(e)) == x**2 + 2 * x + 1


def test_complexity_custom_penalizes_cos():
    # Mathematica-style ComplexityFunction: make cos very expensive, so the
    # unsimplified sin(3x)/sin(x) wins over 2*cos(2x)+1.
    e = sin(3 * x) / sin(x)
    assert MaxSymp(e) == 2 * cos(2 * x) + 1
    penalize_cos = lambda e: 100 * str(e).count("cos") + count_ops(e)
    assert MaxSymp(e, complexity=penalize_cos) == e
