"""setup.py: install MaxSymp Python modules, then use-or-install Maxima.

After installing the Python modules, unless $MAXSIMP_SKIP_MAXIMA=1, reuse an
existing Maxima (env $MAXSIMP_MAXIMA_BIN, package-local maxima-local, or PATH)
or build Maxima from source into <install_lib>/maxima-local. Any failure is
fatal (never silently ignored). Uses stdlib only besides setuptools.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from setuptools import setup
from setuptools.command.install import install


class InstallWithMaxima(install):
    def run(self):
        super().run()
        if os.environ.get("MAXSIMP_SKIP_MAXIMA") == "1":
            print("MAXSIMP_SKIP_MAXIMA=1: skipping Maxima bootstrap.")
            return
        import maxsimp_bootstrap as boot

        existing = boot.find_maxima_bin()
        if existing:
            print(f"maxsimp: using existing Maxima: {existing}")
            return
        prefix = os.path.join(self.install_lib, "maxima-local")
        print(f"maxsimp: no Maxima found; building from source -> {prefix}")
        boot.build_maxima(prefix)
        print(f"maxsimp: Maxima built: {prefix}/bin/maxima")


setup(
    py_modules=["maxsymp", "maxsimp_bootstrap"],
    cmdclass={"install": InstallWithMaxima},
)
