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


def test_check_prerequisites_lisp_optional_bootstrapped_later(monkeypatch):
    # No Lisp on PATH is fine: ensure_lisp() installs SBCL automatically.
    _which_map(monkeypatch, {"gcc", "make"})
    assert boot.check_prerequisites()["lisp"] is None


def test_check_prerequisites_missing_tools_lists_each(monkeypatch):
    _which_map(monkeypatch, set())
    with pytest.raises(RuntimeError) as ei:
        boot.check_prerequisites()
    msg = str(ei.value)
    assert "Lisp" not in msg and "C compiler" in msg and "make" in msg


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


def test_ensure_lisp_prefers_sbcl_no_download(monkeypatch, tmp_path):
    _which_map(monkeypatch, {"sbcl", "clisp"})
    monkeypatch.setattr(boot, "install_sbcl",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not download")))
    assert boot.ensure_lisp(tmp_path / "sbcl") == ("sbcl", None)


def test_ensure_lisp_falls_back_to_clisp(monkeypatch, tmp_path):
    _which_map(monkeypatch, {"clisp"})
    assert boot.ensure_lisp(tmp_path / "sbcl") == ("clisp", None)


def test_ensure_lisp_bootstraps_sbcl_when_none(monkeypatch, tmp_path):
    _which_map(monkeypatch, set())
    seen = {}

    def fake_install(prefix, **k):
        seen["home"] = str(prefix)
        return str(prefix) + "/bin/sbcl"

    monkeypatch.setattr(boot, "install_sbcl", fake_install)
    name, binary = boot.ensure_lisp(tmp_path / "sbcl")
    assert (name, binary) == ("sbcl", str(tmp_path / "sbcl") + "/bin/sbcl")
    assert seen["home"] == str(tmp_path / "sbcl")


def test_sbcl_url_pattern_and_override(monkeypatch):
    monkeypatch.delenv("MAXSIMP_SBCL_URL", raising=False)
    monkeypatch.setattr(boot.platform, "machine", lambda: "x86_64")
    url = boot.sbcl_url("2.6.8")
    assert url == ("https://sourceforge.net/projects/sbcl/files/sbcl/2.6.8/"
                   "sbcl-2.6.8-x86-64-linux-binary.tar.bz2/download")
    monkeypatch.setenv("MAXSIMP_SBCL_URL", "https://example.com/sbcl.tar.bz2")
    assert boot.sbcl_url("2.6.8") == "https://example.com/sbcl.tar.bz2"


def test_sbcl_url_unknown_arch_is_fatal(monkeypatch):
    monkeypatch.delenv("MAXSIMP_SBCL_URL", raising=False)
    monkeypatch.setattr(boot.platform, "machine", lambda: "mips")
    with pytest.raises(RuntimeError, match="No prebuilt SBCL"):
        boot.sbcl_url("2.6.8")


def test_install_sbcl_runs_install_sh_with_prefix(monkeypatch, tmp_path):
    from pathlib import Path

    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.setattr(boot.urllib.request, "urlretrieve",
                        lambda url, dst: Path(dst).write_bytes(b"fake"))
    monkeypatch.setattr(boot.platform, "machine", lambda: "x86_64")

    class FakeTar:
        def __enter__(self):
            (work / "install.sh").write_text("#!/bin/sh\n")
            return self

        def __exit__(self, *a):
            return False

        def extractall(self, dest):
            pass

    monkeypatch.setattr(boot.tarfile, "open", lambda *a, **k: FakeTar())
    cmds = []
    monkeypatch.setattr(boot.subprocess, "run",
                        lambda cmd, **k: cmds.append(cmd) or _SbclVersion())
    out = boot.install_sbcl(tmp_path / "sbcl", workdir=work)
    assert ["sh", "install.sh", f"--prefix={tmp_path / 'sbcl'}"] in cmds
    assert out == str(tmp_path / "sbcl" / "bin" / "sbcl")


class _SbclVersion:
    stdout = "SBCL 2.6.8"
    stderr = ""


def test_build_maxima_uses_bootstrapped_sbcl_path(monkeypatch, tmp_path):
    from pathlib import Path

    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.setattr(boot, "check_prerequisites",
                        lambda: {"lisp": None, "cc": "/usr/bin/gcc", "make": "/usr/bin/make"})
    monkeypatch.setattr(boot, "ensure_lisp", lambda home: ("sbcl", "/fake/sbcl/bin/sbcl"))
    monkeypatch.setattr(boot.urllib.request, "urlretrieve",
                        lambda url, dst: Path(dst).write_bytes(b"fake"))

    class FakeTar:
        def __enter__(self):
            src = work / f"maxima-{boot.MAXIMA_VERSION}"
            src.mkdir(exist_ok=True)
            (src / "configure").write_text("#!/bin/sh\n")
            return self

        def __exit__(self, *a):
            return False

        def extractall(self, dest):
            pass

    monkeypatch.setattr(boot.tarfile, "open", lambda *a, **k: FakeTar())
    cmds = []
    monkeypatch.setattr(boot, "_run", lambda cmd, cwd: cmds.append(cmd))
    monkeypatch.setattr(boot, "verify_maxima", lambda binpath: binpath)
    out = boot.build_maxima(tmp_path / "maxima-local", workdir=work)
    assert any("--with-sbcl=/fake/sbcl/bin/sbcl" in c for c in cmds)
    assert out == str(tmp_path / "maxima-local" / "bin" / "maxima")
