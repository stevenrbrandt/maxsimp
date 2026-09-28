# requirements.md — MaxSimp (growing, revisited periodically)

Source: concept.md (2026-09-28) + CLAUDE.md workflow + user confirmations.

## 1. Functional goal
- Assume Maxima simplifies better than SymPy.
- Create Python function `MaxSymp(expr)` that:
  1. Translates `expr` (SymPy) to something Maxima understands.
  2. Queries Maxima for simplification.
  3. Brings result back and translates to SymPy format.
- Ship with a set of examples / test cases.

## 2. Workflow constraints (from CLAUDE.md)
- Keep this file growing; revisit for contradictions (ask if contradictory).
- Write tests to verify behavior and avoid regressions.
- Never catch-and-ignore exceptions. If an exception seems ignorable, make it fatal.
- Prefer not to ask before implementing; work sequentially in small pieces.
- Never install software without asking.
- Keep `context.md` for continuity.
- Advise if agent count / workflow should change.

## 3. Current decisions / open questions
- Env checked 2026-09-28: Python 3.13.14, SymPy 1.12.1, `maxima` NOT on PATH.
- Decided: query via `maxima-local/bin/maxima --very-quiet` subprocess, script `display2d:false$ + ratsimp((code))`.
- Decided v1: translation via `sstr` + word-boundary E/pi/I/oo replacements; `**` passed through (Maxima accepts it); back via `parse_maxima`.
- Open: which Maxima simplify entry point? v1 used `ratsimp` only; user 2026-09-28 required `sin^2+cos^2->1`, so pipeline became `trigsimp(ratsimp(...))`. User 2026-09-28 then asked for complex Maxima-only cases: pipeline is now `trigrat(trigsimp(ratsimp(...)))`. Confirmed wins (SymPy 1.12.1 `simplify` leaves untouched): `sin(3x)/sin(x)->2*cos(2x)+1`, `cos(3x)/cos(x)->2*cos(2x)-1`, `sin(5x)/sin(x)->2*cos(4x)+2*cos(2x)+1`.
- User 2026-09-28 asked if Maxima supports a Mathematica-style ComplexityFunction. Finding: no built-in equivalent; emulated in `MaxSymp(expr, complexity=None, candidates=None)`. Default (both None) uses single aggressive `trigrat(trigsimp(ratsimp(...)))` chain; passing `complexity`/`candidates` tries ratsimp, trigsimp+ratsimp, trigrat-chain, factor, radcan and keeps the min-cost form. Lesson: pure `count_ops` would prefer unsimplified `sin(3x)/sin(x)` over `2*cos(2x)+1`, so default stays aggressive.
- User confirmed 2026-09-28: Yes — initialize requirements.md / context.md and break down task.
- User 2026-09-28: Install locally.
- User 2026-09-28: Can you install maxima in the current directory?

## 4. Install decision
- User chose 2026-09-28: Build from source to `./maxima-local` (inside repo dir).
- Implication: needs Lisp (SBCL preferred), gcc/make/autoconf, downloader; long build; prefix set to repo-local path.
- Rule reminder: install approved by user, so proceeding with build steps only.

## 5. Contradiction log
- None yet.

## 8. Pip installer result (2026-09-28)
- Files: `pyproject.toml` (setuptools backend, project `maxsimp` 0.1.0, script `maxsimp-install-maxima`), `setup.py` (custom install: reuse existing Maxima or build into <install_lib>/maxima-local unless MAXSIMP_SKIP_MAXIMA=1), `maxsimp_bootstrap.py` (checks, download, build, discovery, CLI), `test_maxsimp_install.py` (10 mocked tests).
- Runtime `maxsymp._maxima_bin` now delegates to bootstrap discovery; missing binary raises with install instructions.
- Not yet validated: real `pip install .` (env lacks setuptools; needs user approval to install it). 23/23 pytest pass.
- Bug 2026-09-28 (user report: pip install makes no attempt at Maxima): modern pip builds a wheel via PEP 517 and never runs setup.py's `install` cmdclass, so the hook was dead code. Fix: run use-or-install in a `build_py` hook (executes during wheel build, i.e. during `pip install .`), targeting the user data dir (`~/.local/share/maxsimp/maxima-local`, overridable by $MAXSIMP_PREFIX), still skipped by MAXSIMP_SKIP_MAXIMA=1 and fatal on missing tools.
- Bug 2026-09-28 (user log: `pip install -e .` also silent): PEP 660 editable builds run `editable_wheel`, not `build_py`. Fix: same use-or-install call in an `editable_wheel` cmdclass override.
- SBCL fallback 2026-09-28 (user: yes): no Lisp on PATH is no longer fatal; `ensure_lisp()` installs official SBCL 2.6.8 binaries to <prefix>/sbcl. 34/34 pytest pass (21 installer tests, mocked).

## 6. Install result (2026-09-28)
- Built Maxima 5.49.0 from source with `--enable-clisp --disable-build-docs`, prefix `./maxima-local`.
- Verified: `ratsimp((x^2-1)/(x-1))` -> `x+1`.
- Note: help-system warnings about missing maxima-index.lisp are expected (docs disabled); harmless.

## 7. Pip installer (2026-09-28, user request)
- Provide a pip installer for MaxSymp that can use or install Maxima from source.
- Behavior: prefer usable Maxima in order MAXSIMP_MAXIMA_BIN env -> package-local maxima-local -> system PATH; else build from source tarball.
- Must check prerequisites first and fail with a clear error if missing: a C compiler (gcc/cc) and make are fatal. Lisp is soft: prefer sbcl/clisp on PATH, else auto-install official SBCL binaries (pinned 2.6.8, URL verified 2026-09-28; x86_64/arm64) into <prefix>/sbcl, then configure Maxima with --with-sbcl=<path>. Download uses stdlib urllib; extraction uses stdlib tarfile.
- Must not silently ignore failures: any missing tool or failed step is a fatal error with message.
- Provide skip/opt-out for offline installs (env MAXSIMP_SKIP_MAXIMA=1 installs Python only).
- Ship tests for prereq checker and discovery logic (mocked, no real build).
