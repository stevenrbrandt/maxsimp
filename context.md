# context.md — MaxSimp handoff

## Goal
`MaxSymp(expr)`: SymPy -> Maxima -> simplify -> SymPy, with examples/tests.

## Current state (2026-09-28)
- Repo has: `concept.md`, `CLAUDE.md`, `requirements.md`, `context.md`, `maxsymp.py` (new), `test_maxsymp.py` (new).
- Implemented: `MaxSymp(expr, complexity=None, candidates=None)`; 13 pytest tests pass.
- Note 2026-09-28: user corrected trig test to require `sin^2+cos^2->1`; pipeline upgraded from ratsimp-only.
- Note 2026-09-28: added 3 Maxima-only regression tests (triple/quintuple-angle ratios) where SymPy simplify fails.
- Note 2026-09-28: added ComplexityFunction emulation (default aggressive chain; hook searches 5 transformers); 4 new tests cover factored-vs-expanded choice and cos-penalizing custom cost.
- Note 2026-09-28: pip installer added (pyproject.toml, setup.py use-or-install, maxsimp_bootstrap.py, 10 installer tests). Full suite 23/23 pass. Real `pip install .` validation pending (no setuptools in env; install needs user approval).
- Note 2026-09-28: initial git commit created (maxima-local/ excluded via .gitignore).
- Note 2026-09-28: fixed pip-install Maxima bootstrap — setup.py `install` hook never runs under PEP 517 wheels, so use-or-install moved to a `build_py` hook via `boot.maybe_use_or_install()` (default prefix ~/.local/share, $MAXSIMP_PREFIX override, $MAXSIMP_SKIP_MAXIMA=1 opt-out). Suite 27/27 pass. Not committed; user re-validates `pip install .`.
- Note 2026-09-28: user log shows `pip install -e .` also silent (PEP 660 runs `editable_wheel`, not `build_py`); added EditableWheelWithMaxima hook. Uncommitted pending user go-ahead.
- Note 2026-09-28: SBCL fallback implemented (ensure_lisp/install_sbcl/verify_sbcl, --with-sbcl wiring); suite 34/34 pass. Uncommitted.
- Env: Python 3.13.14, SymPy 1.12.1, Maxima 5.49.0 at `./maxima-local/bin/maxima`.

## Key blocker (resolved 2026-09-28)
- Maxima 5.49.0 built to `./maxima-local/bin/maxima` (clisp backend). Verified working.
- Source kept at /tmp/opencode/maxima-5.49.0 + tarball.

## Next pieces (small, sequential)
1. Resolve Maxima availability.
2. Spike: SymPy -> Maxima string translation (check `sympy.printing` for maxima support).
3. Spike: minimal Maxima batch call + capture output.
4. Spike: Maxima output -> SymPy (`sympify` / parse).
5. Implement `MaxSymp(expr)` skeleton with no silent exception handling.
6. Add examples/test cases from concept.md.
7. Run tests, iterate.

## Notes for next AI
- Re-read `requirements.md` before each change; update it if instructions grow.
- Keep pieces small; do one spike at a time.
- Single agent is sufficient right now; suggest more only if parallel spikes are wanted.
