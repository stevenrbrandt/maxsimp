"""Tests for the pip-installer bootstrap (mocked; never builds or downloads)."""

import pytest

import maxsimp_bootstrap as boot
from maxsymp import _wrap


def _which_map(monkeypatch, present):
    monkeypatch.setattr(boot, "_which", lambda name: f"/usr/bin/{name}" if name in present else None)


def test_check_prerequisites_ok(monkeypatch):
    _which_map(monkeypatch, {"clisp", "gcc", "make"})
    assert boot.check_prerequisites() == {"lisp": "clisp", "cc": "/usr/bin/gcc", "make": "/usr/bin/make"}


def test_check_prerequisites_prefers_sbcl(monkeypatch):
    _which_map(monkeypatch, {"sbcl", "clisp", "cc", "make"})
    assert boot.check_prerequisites()["lisp"] == "sbcl"


def test_check_prerequisites_missing_lisp_is_fatal(monkeypatch):
    _which_map(monkeypatch, {"gcc", "make"})
    with pytest.raises(RuntimeError, match="Lisp"):
        boot.check_prerequisites()


def test_check_prerequisites_missing_all_lists_each(monkeypatch):
    _which_map(monkeypatch, set())
    with pytest.raises(RuntimeError) as ei:
        boot.check_prerequisites()
    msg = str(ei.value)
    assert "Lisp" in msg and "C compiler" in msg and "make" in msg


def test_build_fails_fast_without_prereqs_no_download(monkeypatch, tmp_path):
    _which_map(monkeypatch, set())
    with pytest.raises(RuntimeError, match="prerequisites"):
        boot.build_maxima(tmp_path / "maxima-local")


def test_find_prefers_env(monkeypatch, tmp_path):
    fake = tmp_path / "maxima"
    fake.write_text("#!/bin/sh\n")
    monkeypatch.setenv("MAXSIMP_MAXIMA_BIN", str(fake))
    assert boot.find_maxima_bin() == str(fake)


def test_find_package_local_before_path(monkeypatch, tmp_path):
    monkeypatch.delenv("MAXSIMP_MAXIMA_BIN", raising=False)
    local = tmp_path / "maxima-local" / "bin" / "maxima"
    local.parent.mkdir(parents=True)
    local.write_text("#!/bin/sh\n")
    monkeypatch.setattr(boot, "package_local_bin", lambda: local)
    monkeypatch.setattr(boot, "user_data_bin", lambda: tmp_path / "nope")
    monkeypatch.setattr(boot, "_which", lambda name: "/usr/bin/maxima")
    assert boot.find_maxima_bin() == str(local)


def test_find_none_when_nothing_present(monkeypatch, tmp_path):
    monkeypatch.delenv("MAXSIMP_MAXIMA_BIN", raising=False)
    monkeypatch.setattr(boot, "package_local_bin", lambda: tmp_path / "nope1")
    monkeypatch.setattr(boot, "user_data_bin", lambda: tmp_path / "nope2")
    monkeypatch.setattr(boot, "_which", lambda name: None)
    assert boot.find_maxima_bin() is None


def test_ensure_raises_helpful_error(monkeypatch, tmp_path):
    monkeypatch.delenv("MAXSIMP_MAXIMA_BIN", raising=False)
    monkeypatch.setattr(boot, "package_local_bin", lambda: tmp_path / "nope1")
    monkeypatch.setattr(boot, "user_data_bin", lambda: tmp_path / "nope2")
    monkeypatch.setattr(boot, "_which", lambda name: None)
    with pytest.raises(FileNotFoundError, match="maxsimp-install-maxima"):
        boot.ensure_maxima_bin()


def test_wrap_unknown_is_fatal():
    with pytest.raises(ValueError, match="Unknown Maxima candidate"):
        _wrap("x", "nope")


def test_maybe_skips_when_env_set(monkeypatch):
    monkeypatch.setenv("MAXSIMP_SKIP_MAXIMA", "1")
    monkeypatch.setattr(boot, "build_maxima", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not build")))
    assert boot.maybe_use_or_install() is None


def test_maybe_reuses_existing_without_build(monkeypatch):
    monkeypatch.delenv("MAXSIMP_SKIP_MAXIMA", raising=False)
    monkeypatch.setattr(boot, "find_maxima_bin", lambda: "/usr/bin/maxima")
    monkeypatch.setattr(boot, "build_maxima", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not build")))
    assert boot.maybe_use_or_install() == "/usr/bin/maxima"


def test_maybe_builds_to_default_prefix(monkeypatch, tmp_path):
    monkeypatch.delenv("MAXSIMP_SKIP_MAXIMA", raising=False)
    monkeypatch.delenv("MAXSIMP_PREFIX", raising=False)
    monkeypatch.setattr(boot, "find_maxima_bin", lambda: None)
    seen = {}

    def fake_build(prefix, **k):
        seen["prefix"] = str(prefix)
        return str(prefix) + "/bin/maxima"

    monkeypatch.setattr(boot, "build_maxima", fake_build)
    out = boot.maybe_use_or_install()
    assert seen["prefix"] == str(boot.default_prefix())
    assert out.endswith("bin/maxima")


def test_default_prefix_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("MAXSIMP_PREFIX", str(tmp_path / "custom"))
    assert boot.default_prefix() == tmp_path / "custom"
