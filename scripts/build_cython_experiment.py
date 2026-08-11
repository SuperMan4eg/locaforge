"""Build an isolated Cython version of one measured pure-Python service."""

from pathlib import Path

from Cython.Build import cythonize
from setuptools import Extension, setup

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE = PROJECT_ROOT / "src/locaforge/application/services/consistency_validator.py"


setup(
    name="locaforge-stage7-cython-experiment",
    ext_modules=cythonize(
        [Extension("stage7_consistency_validator", [str(SOURCE)])],
        build_dir=str(PROJECT_ROOT / "build/stage7-cython/generated"),
        force=True,
        compiler_directives={
            "language_level": "3",
            "binding": True,
            "always_allow_keywords": False,
            "annotation_typing": False,
        },
        annotate=True,
    ),
)
