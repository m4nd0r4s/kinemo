"""Lints that run after the build.

- `visual`: W10xx readability lints computed by the core (`kinemo-resolve`) by sampling
  the timeline, turned into diagnostics located at the objects' source lines.
- `code`: W03xx lints found in the scene function's AST, without running it.

`kinemo.lints.run_lints` is the entry point that combines them with layout errors.
"""

from .code import code_diagnostics
from .visual import visual_diagnostics

__all__ = ["code_diagnostics", "visual_diagnostics"]
