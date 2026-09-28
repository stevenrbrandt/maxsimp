"""MaxSymp: simplify SymPy expressions via local Maxima.

Pipeline: SymPy -> Maxima string -> try several Maxima transformers,
pick the result minimizing `complexity` (Mathematica-style ComplexityFunction).
Requires: ./maxima-local built from source (Maxima 5.49.0, clisp backend).
"""

import re
import subprocess
from pathlib import Path

from sympy import count_ops, sstr
from sympy.parsing.maxima import parse_maxima

import maxsimp_bootstrap as _boot

_LOCAL_BIN = Path(__file__).resolve().parent / "maxima-local" / "bin" / "maxima"


def _maxima_bin() -> str:
    found = _boot.find_maxima_bin()
    if found:
        return found
    raise FileNotFoundError(
        f"No usable Maxima found (looked in $MAXSIMP_MAXIMA_BIN, {_LOCAL_BIN}, "
        f"{_boot.user_data_bin()}, and PATH). Build one from source with "
        "'maxsimp-install-maxima' (pip installs the 'maxsimp' package first)."
    )


def sympy_to_maxima(expr) -> str:
    """Translate a SymPy expression to Maxima input syntax (v1, minimal)."""
    s = sstr(expr)
    # Word-boundary replacements so user symbols like 'pie' or 'Inner' survive.
    s = re.sub(r"\bE\b", "%e", s)
    s = re.sub(r"\bpi\b", "%pi", s)
    s = re.sub(r"\bI\b", "%i", s)
    s = re.sub(r"\b-oo\b", "-minf", s)
    s = re.sub(r"\boo\b", "inf", s)
    return s


# Candidate Maxima transformers, tried in order (ties keep the earliest).
# Each takes the translated code string and wraps it.
_CANDIDATES = (
    "ratsimp",
    "trigsimp_ratsimp",
    "trigrat_trigsimp_ratsimp",
    "factor",
    "radcan",
)


def _wrap(code: str, name: str) -> str:
    if name == "ratsimp":
        return f"ratsimp(({code}))"
    if name == "trigsimp_ratsimp":
        return f"trigsimp(ratsimp(({code})))"
    if name == "trigrat_trigsimp_ratsimp":
        return f"trigrat(trigsimp(ratsimp(({code}))))"
    if name == "factor":
        return f"factor(({code}))"
    if name == "radcan":
        return f"radcan(({code}))"
    raise ValueError(f"Unknown Maxima candidate: {name!r}")


def default_complexity(expr) -> int:
    """Default cost function: number of operations (lower is simpler)."""
    return int(count_ops(expr))


def run_maxima(code: str, timeout: int = 60) -> str:
    """Backward-compatible entry: full trigrat chain for a pre-translated `code`."""
    return run_maxima_transform(code, "trigrat_trigsimp_ratsimp", timeout=timeout)


def run_maxima_transform(code: str, transform: str, timeout: int = 60) -> str:
    """Send one wrapped `transform` of pre-translated `code` to Maxima batch."""
    script = f"display2d:false$\n{_wrap(code, transform)};\nquit();\n"
    proc = subprocess.run(
        [_maxima_bin(), "--very-quiet"],
        input=script,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=True,
    )
    lines = []
    for line in proc.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("WARNING"):
            continue
        if stripped.startswith("(Details"):
            continue
        if "does not exist" in stripped:
            continue
        if "share/info" in stripped:
            continue
        lines.append(stripped)
    if not lines:
        raise RuntimeError(f"Maxima produced no parseable output for: {code!r}\nstdout={proc.stdout!r}\nstderr={proc.stderr!r}")
    return lines[-1]


def maxima_to_sympy(s: str):
    """Translate Maxima output string back to a SymPy expression."""
    return parse_maxima(s)


def MaxSymp(expr, timeout: int = 60, complexity=None, candidates=None):
    """Simplify SymPy `expr` via Maxima, keeping the lowest-`complexity` form.

    `complexity` is a Mathematica-style ComplexityFunction: callable taking a
    SymPy expression and returning a number (lower is simpler). With the
    default (`complexity=None`, `candidates=None`) a single aggressive
    pipeline `trigrat(trigsimp(ratsimp(...)))` is used. Passing `complexity`
    (or `candidates`) instead tries each candidate transformer and returns
    the form minimizing `complexity` (default cost: operation count).
    `candidates` optionally overrides the Maxima transformer names tried
    (subset of "ratsimp", "trigsimp_ratsimp",
    "trigrat_trigsimp_ratsimp", "factor", "radcan").
    """
    code = sympy_to_maxima(expr)
    if complexity is None and candidates is None:
        return maxima_to_sympy(
            run_maxima_transform(code, "trigrat_trigsimp_ratsimp", timeout=timeout)
        )
    if complexity is None:
        complexity = default_complexity
    names = list(candidates) if candidates is not None else list(_CANDIDATES)
    if not names:
        raise ValueError("candidates must list at least one transformer")
    best = None
    best_cost = None
    for name in names:
        raw = run_maxima_transform(code, name, timeout=timeout)
        result = maxima_to_sympy(raw)
        cost = complexity(result)
        if best is None or cost < best_cost:
            best = result
            best_cost = cost
    return best
