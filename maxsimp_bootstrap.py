"""Bootstrap helper: use or install a Maxima binary for MaxSimp.

Resolution order for an existing binary (see find_maxima_bin):
  1. $MAXSIMP_MAXIMA_BIN (explicit path)
  2. package-local maxima-local/bin/maxima (dev checkout or pip install target)
  3. ~/.local/share/maxsimp/maxima-local/bin/maxima (console-script default)
  4. `maxima` on PATH

If none is usable, build_maxima() downloads the Maxima source tarball and
builds it with --prefix=<prefix>. It needs a C compiler and make (fatal if
missing); for Lisp it prefers sbcl/clisp on PATH and otherwise downloads an
official SBCL binary tarball into <prefix>/sbcl automatically.
Any missing prerequisite or failed step raises (never silently ignored).

Installed as the `maxsimp-install-maxima` console script.
"""

import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

MAXIMA_VERSION = os.environ.get("MAXSIMP_MAXIMA_VERSION", "5.49.0")
MAXIMA_URL = os.environ.get(
    "MAXSIMP_MAXIMA_URL",
    f"https://sourceforge.net/projects/maxima/files/Maxima-source/"
    f"{MAXIMA_VERSION}-source/maxima-{MAXIMA_VERSION}.tar.gz/download",
)

SBCL_VERSION = os.environ.get("MAXSIMP_SBCL_VERSION", "2.6.8")
# Older-glibc fallback builds (unofficial roswell mirror, pinned; SBCL version
# only matters as a Maxima build host).
_SBCL_FALLBACK_VERSION = "2.6.6"
_SBCL_ARCH_TOKENS = {"x86_64": "x86-64", "aarch64": "arm64", "arm64": "arm64"}


def _glibc_version() -> tuple:
    lib, ver = platform.libc_ver()
    parts = (ver or "").split(".")
    try:
        return (lib, (int(parts[0]), int(parts[1])))
    except (IndexError, ValueError):
        return (lib, None)


def sbcl_url(version: str = SBCL_VERSION, arch_token: str = None) -> str:
    """Download URL for an SBCL Linux binary tarball compatible with this host.

    $MAXSIMP_SBCL_URL overrides everything. Otherwise x86_64 hosts get the
    official build on new glibc (>= 2.39) or a roswell glibc-matched build
    (2.31/2.23 variants) on older ones; other arches get the official build.
    """
    env = os.environ.get("MAXSIMP_SBCL_URL")
    if env:
        return env
    if arch_token is None:
        machine = platform.machine()
        if machine not in _SBCL_ARCH_TOKENS:
            raise RuntimeError(
                f"No prebuilt SBCL for architecture {machine!r}; "
                "install sbcl or clisp manually (e.g. sudo apt install sbcl)."
            )
        arch_token = _SBCL_ARCH_TOKENS[machine]
    if arch_token == "x86-64":
        lib, ver = _glibc_version()
        if lib == "glibc" and ver is not None:
            if ver >= (2, 39):
                pass  # official build below
            else:
                variant = "glibc2.31" if ver >= (2, 31) else "glibc2.23" if ver >= (2, 23) else None
                if variant is None:
                    raise RuntimeError(
                        f"glibc {ver[0]}.{ver[1]} too old for prebuilt SBCL; "
                        "install sbcl or clisp manually (e.g. sudo apt install sbcl)."
                    )
                fv = _SBCL_FALLBACK_VERSION
                return (
                    f"https://github.com/roswell/sbcl_bin/releases/download/{fv}/"
                    f"sbcl-{fv}-{arch_token}-linux-{variant}-binary.tar.bz2"
                )
        elif lib != "glibc":
            raise RuntimeError(
                f"Non-glibc system ({lib}); set $MAXSIMP_SBCL_URL to a musl SBCL "
                "binary or install sbcl/clisp manually."
            )
    return (
        f"https://sourceforge.net/projects/sbcl/files/sbcl/{version}/"
        f"sbcl-{version}-{arch_token}-linux-binary.tar.bz2/download"
    )

_USER_PREFIX = Path.home() / ".local" / "share" / "maxsimp" / "maxima-local"


def default_prefix() -> Path:
    """Install prefix for Maxima builds; overridable by $MAXSIMP_PREFIX."""
    env = os.environ.get("MAXSIMP_PREFIX")
    return Path(env) if env else _USER_PREFIX


def maybe_use_or_install(prefix=None):
    """Use an existing Maxima or build from source; return bin path or None if skipped.

    Returns None without doing anything when $MAXSIMP_SKIP_MAXIMA=1.
    Otherwise reuses find_maxima_bin() when present, else build_maxima(prefix).
    Any failure raises (never silently ignored).
    """
    if os.environ.get("MAXSIMP_SKIP_MAXIMA") == "1":
        print("MAXSIMP_SKIP_MAXIMA=1: skipping Maxima bootstrap.")
        return None
    existing = find_maxima_bin()
    if existing:
        print(f"maxsimp: using existing Maxima: {existing}")
        return existing
    target = Path(prefix) if prefix else default_prefix()
    print(f"maxsimp: no Maxima found; building from source -> {target}")
    built = build_maxima(target)
    print(f"maxsimp: Maxima ready: {built}")
    return built


def _which(name: str):
    return shutil.which(name)


def check_prerequisites() -> dict:
    """Verify hard build tools exist; return them or raise RuntimeError.

    Lisp is NOT required here: ensure_lisp() bootstraps SBCL when neither
    sbcl nor clisp is on PATH. Only a C compiler and make are fatal.
    """
    lisp = None
    for cand in ("sbcl", "clisp"):
        if _which(cand):
            lisp = cand
            break
    cc = _which("gcc") or _which("cc")
    make = _which("make")
    missing = []
    if cc is None:
        missing.append("a C compiler (install gcc, e.g. sudo apt install gcc)")
    if make is None:
        missing.append("make (e.g. sudo apt install make)")
    if missing:
        raise RuntimeError(
            "Cannot build Maxima from source; missing prerequisites:\n"
            + "\n".join(f"  - {m}" for m in missing)
        )
    return {"lisp": lisp, "cc": cc, "make": make}


def install_sbcl(prefix, version: str = SBCL_VERSION, url: str = None,
                 workdir=None) -> str:
    """Download the official SBCL binary tarball and install to `prefix`.

    Returns the installed `sbcl` binary path. Raises on any failure.
    """
    prefix = Path(prefix)
    url = url or sbcl_url(version)
    tmp = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="maxsimp-sbcl-"))
    tmp.mkdir(parents=True, exist_ok=True)
    tarball = tmp / f"sbcl-{version}-linux-binary.tar.bz2"
    if not tarball.exists():
        urllib.request.urlretrieve(url, tarball)
    with tarfile.open(tarball, "r:bz2") as tf:
        tf.extractall(tmp)
    # The binary tarball nests everything under sbcl-<ver>-<arch>-linux/.
    matches = sorted(tmp.rglob("install.sh"))
    if not matches:
        raise RuntimeError(f"SBCL archive did not unpack as expected in {tmp}")
    install_dir = matches[0].parent
    _run(["sh", "install.sh", f"--prefix={prefix}"], install_dir)
    return verify_sbcl(str(prefix / "bin" / "sbcl"))


def verify_sbcl(binpath: str, timeout: int = 60) -> str:
    """Check `binpath` runs; return it or raise with full diagnostics."""
    proc = subprocess.run(
        [binpath, "--version"], capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0 or "SBCL" not in proc.stdout:
        raise RuntimeError(
            f"SBCL smoke test failed for {binpath!r}:\n"
            f"returncode={proc.returncode}\nstdout={proc.stdout!r}\n"
            f"stderr={proc.stderr!r}\n"
            "Likely causes: binary/glibc mismatch (try $MAXSIMP_SBCL_URL with an "
            "older-glibc build) or missing shared libraries (check `ldd <bin>`)."
        )
    return binpath


def ensure_lisp(sbcl_home) -> tuple:
    """Return (name, bin_path_or_None) for a usable Lisp.

    Prefers sbcl then clisp on PATH; otherwise installs SBCL binaries to
    `sbcl_home`. `bin_path_or_None` is None when using a PATH Lisp.
    """
    if _which("sbcl"):
        return ("sbcl", None)
    if _which("clisp"):
        return ("clisp", None)
    print(f"maxsimp: no Lisp on PATH; installing SBCL {SBCL_VERSION} -> {sbcl_home}")
    return ("sbcl", install_sbcl(sbcl_home))


def _configure_args(lisp: str, sbcl_bin=None) -> list:
    if lisp == "clisp":
        return ["--enable-clisp", "--disable-build-docs"]
    if lisp == "sbcl":
        if sbcl_bin:
            return [f"--with-sbcl={sbcl_bin}", "--disable-build-docs"]
        return ["--disable-build-docs"]
    raise ValueError(f"Unsupported Lisp for Maxima build: {lisp!r}")


def _run(cmd, cwd) -> None:
    subprocess.run(cmd, cwd=str(cwd), check=True)


def build_maxima(prefix, version: str = MAXIMA_VERSION, url: str = MAXIMA_URL,
                 workdir=None) -> str:
    """Download Maxima `version` source and install to `prefix`; return maxima bin path."""
    tools = check_prerequisites()
    prefix = Path(prefix)
    lisp_name, lisp_bin = ensure_lisp(prefix / "sbcl")
    tmp = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="maxsimp-maxima-"))
    tmp.mkdir(parents=True, exist_ok=True)
    tarball = tmp / f"maxima-{version}.tar.gz"
    if not tarball.exists():
        urllib.request.urlretrieve(url, tarball)
    with tarfile.open(tarball, "r:gz") as tf:
        tf.extractall(tmp)
    src = tmp / f"maxima-{version}"
    if not (src / "configure").exists():
        raise RuntimeError(f"Maxima source did not unpack as expected in {src}")
    _run(["./configure", f"--prefix={prefix}",
          *_configure_args(lisp_name, lisp_bin)], src)
    _run([tools["make"], "-j4"], src)
    _run([tools["make"], "install"], src)
    return verify_maxima(str(prefix / "bin" / "maxima"))


def verify_maxima(binpath: str, timeout: int = 120) -> str:
    """Smoke-test `binpath`; return it or raise if it cannot simplify."""
    script = "display2d:false$\nratsimp(((x**2-1)/(x-1)));\nquit();\n"
    proc = subprocess.run(
        [binpath, "--very-quiet"], input=script, capture_output=True,
        text=True, timeout=timeout, check=True,
    )
    if "x+1" not in proc.stdout.replace(" ", ""):
        raise RuntimeError(
            f"Maxima smoke test failed for {binpath!r}:\nstdout={proc.stdout!r}\n"
            f"stderr={proc.stderr!r}"
        )
    return binpath


def package_local_bin() -> Path:
    return Path(__file__).resolve().parent / "maxima-local" / "bin" / "maxima"


def user_data_bin() -> Path:
    return _USER_PREFIX / "bin" / "maxima"


def find_maxima_bin():
    """Return the first usable Maxima binary path, or None if there is none."""
    env = os.environ.get("MAXSIMP_MAXIMA_BIN")
    if env and Path(env).exists():
        return str(Path(env))
    for cand in (package_local_bin(), user_data_bin()):
        if cand.exists():
            return str(cand)
    found = _which("maxima")
    if found:
        return found
    return None


def ensure_maxima_bin() -> str:
    """Return a usable Maxima path or raise FileNotFoundError with instructions."""
    found = find_maxima_bin()
    if found:
        return found
    raise FileNotFoundError(
        "No usable Maxima found. Either install it (sudo apt install maxima), "
        "point $MAXSIMP_MAXIMA_BIN at a maxima binary, or build from source with:\n"
        "  maxsimp-install-maxima"
    )


def main(argv=None) -> int:
    """Entry point for `maxsimp-install-maxima`; exits non-zero on any failure."""
    import argparse

    ap = argparse.ArgumentParser(description="Use or install Maxima for MaxSimp.")
    ap.add_argument("--prefix", default=str(_USER_PREFIX),
                    help="install prefix (default: %(default)s)")
    ap.add_argument("--version", default=MAXIMA_VERSION)
    ap.add_argument("--url", default=MAXIMA_URL)
    ap.add_argument("--workdir", default=None)
    ap.add_argument("--force", action="store_true",
                    help="rebuild even if a usable Maxima already exists")
    args = ap.parse_args(argv)
    existing = find_maxima_bin()
    if existing and not args.force:
        print(f"Using existing Maxima: {existing}")
        return 0
    tools = check_prerequisites()
    lisp_desc = tools["lisp"] or f"bootstrapped SBCL {SBCL_VERSION}"
    print(f"Building Maxima {args.version} with {lisp_desc} -> {args.prefix}")
    built = build_maxima(args.prefix, version=args.version, url=args.url,
                         workdir=args.workdir)
    print(f"Maxima ready: {built}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
