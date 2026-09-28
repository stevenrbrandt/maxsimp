"""setup.py: install MaxSymp Python modules, then use-or-install Maxima.

`pip install .` builds a wheel via PEP 517, which runs the `build_py`
command but never the legacy `install` command -- so the Maxima bootstrap
lives here in `build_py` (plus the `maxsimp-install-maxima` console script
for explicit builds). Unless $MAXSIMP_SKIP_MAXIMA=1, reuse an existing
Maxima or build from source into $MAXSIMP_PREFIX (default
~/.local/share/maxsimp/maxima-local). Any failure is fatal (never silently
ignored). Uses stdlib only besides setuptools.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from setuptools import setup
from setuptools.command.build_py import build_py


class BuildPyWithMaxima(build_py):
    def run(self):
        super().run()
        import maxsimp_bootstrap as boot

        boot.maybe_use_or_install()


setup(
    py_modules=["maxsymp", "maxsimp_bootstrap"],
    cmdclass={"build_py": BuildPyWithMaxima},
)
