"""Static typing of the public API (spec: "Full typing").

- User-style scenes (`tests/typing/` and every file in `examples/`) and every docs
  example pass Pyright in strict mode.
- Every public symbol (`kinemo.__all__` and the public members of exported classes) has a
  known type, and `Any` appears only where the API is deliberately dynamic.
- Object props declared for the type checker (`if TYPE_CHECKING:` blocks on each class)
  cover the props the runtime resolves from `PROPS`, with matching value types.

The Pyright tests are skipped when Pyright is not installed.
"""

from __future__ import annotations

import ast
import inspect
import json
import re
import shutil
import subprocess
import textwrap
from pathlib import Path
from typing import Any, TypeVar

import pytest

import kinemo as k
from kinemo.component.component import Component
from kinemo.docs import catalog
from kinemo.objects.node import Node

ROOT = Path(__file__).resolve().parents[2]
TYPING_PROJECT = ROOT / "tests" / "typing" / "pyrightconfig.json"

#: Public symbols whose type deliberately contains `Any` (keep this list short).
DYNAMIC_PUBLIC_SYMBOLS = {
    "k.list",  # `k.list()` starts empty and holds any item
    "k.context",  # `k.context(name)` without a default
    "k.field",  # `k.field(choices=...)` without a default
    "k.from_context",  # the same marker is the default of props and of static fields
}

#: Members that exist only at runtime, to turn classic mistakes into diagnostics
#: (`(x + 1).to(3)` → K0303); the type checker reports them statically instead.
RUNTIME_ONLY_MEMBERS = {("Expr", "set"), ("Expr", "to")}

#: Annotation of `PropAccessor[...]` expected for each prop kind.
KIND_TYPES = {
    "float": "float",
    "bool": "bool",
    "str": "str",
    "color": "Color",
    "vec2": "Vec",
    "points": "list[Vec]",
    "floats": "list[float]",
    "segments": "list[list[Vec]]",
    "object": "int",
}


# ---- pyright --------------------------------------------------------------------------


def _pyright_command() -> list[str]:
    local = ROOT / ".venv" / "bin" / "pyright"
    if local.exists():
        return [str(local)]
    found = shutil.which("pyright")
    if found is None:
        pytest.skip("pyright is not installed")
    return [found]


def _pyright(project: Path) -> list[dict[str, Any]]:
    """Diagnostics of `pyright --outputjson -p project` (errors and `reveal_type` notes)."""
    result = subprocess.run(
        [*_pyright_command(), "--outputjson", "-p", str(project)],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=600,
        encoding="utf-8",
    )
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError:
        pytest.fail(f"pyright did not produce a report:\n{result.stdout}\n{result.stderr}")
    return report["generalDiagnostics"]


def _errors(diagnostics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [d for d in diagnostics if d["severity"] == "error"]


def _describe(diagnostics: list[dict[str, Any]]) -> str:
    return "\n".join(
        f"{Path(d['file']).name}:{d['range']['start']['line'] + 1}: {d['message'].splitlines()[0]}"
        for d in diagnostics
    )


def _strict_project(directory: Path, *, report_unused_variables: bool = True) -> Path:
    """A strict Pyright project over `directory` that imports kinemo from this checkout."""
    config: dict[str, Any] = {
        "include": ["."],
        "extraPaths": [str(ROOT / "python")],
        "pythonVersion": "3.11",
        "typeCheckingMode": "strict",
    }
    if (ROOT / ".venv").exists():
        config.update(venvPath=str(ROOT), venv=".venv")
    if not report_unused_variables:
        # Docs examples bind objects to names so diagnostics read `grid`, not `grid#3`.
        config["reportUnusedVariable"] = False
    path = directory / "pyrightconfig.json"
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return path


def test_user_scenes_pass_pyright_strict() -> None:
    errors = _errors(_pyright(TYPING_PROJECT))
    assert not errors, "Pyright strict errors in tests/typing or examples/:\n" + _describe(errors)


def test_docs_examples_pass_pyright_strict(tmp_path: Path) -> None:
    for i, entry in enumerate(catalog.entries()):
        name = re.sub(r"\W+", "_", entry.symbol).strip("_").lower()
        (tmp_path / f"example_{i:03d}_{name}.py").write_text(entry.example, encoding="utf-8")
    errors = _errors(_pyright(_strict_project(tmp_path, report_unused_variables=False)))
    assert not errors, "Pyright strict errors in docs examples:\n" + _describe(errors)


def _type_argument(parameter: object) -> str:
    """What to specialize a generic class with to read its members (`k.Group[k.Node]`)."""
    bound = getattr(parameter, "__bound__", None)
    if isinstance(parameter, TypeVar) and bound is not None and getattr(k, bound.__name__, None) is bound:
        return f"k.{bound.__name__}"
    return "object"


def _surface_lines() -> list[str]:
    lines = ["import kinemo as k", "from typing import reveal_type", ""]
    for name in k.__all__:
        obj = getattr(k, name)
        lines.append(f"reveal_type(k.{name})")
        if not inspect.isclass(obj):
            continue
        parameters = getattr(obj, "__parameters__", ())
        owner = f"k.{name}[{', '.join(_type_argument(p) for p in parameters)}]" if parameters else f"k.{name}"
        for member in sorted(vars(obj)):
            if not member.startswith("_") and (name, member) not in RUNTIME_ONLY_MEMBERS:
                lines.append(f"reveal_type({owner}.{member})")
    return lines


def test_public_surface_is_fully_typed(tmp_path: Path) -> None:
    lines = _surface_lines()
    (tmp_path / "surface.py").write_text("\n".join(lines) + "\n", encoding="utf-8")
    diagnostics = _pyright(_strict_project(tmp_path))
    errors = _errors(diagnostics)
    assert not errors, "public symbols with unknown types:\n" + _describe(errors)
    with_any = {
        lines[d["range"]["start"]["line"]][len("reveal_type(") : -1]
        for d in diagnostics
        if d["severity"] == "information" and re.search(r"\bAny\b", d["message"])
    }
    unexpected = sorted(with_any - DYNAMIC_PUBLIC_SYMBOLS)
    assert not unexpected, f"public symbols typed with Any: {unexpected}"


# ---- prop declarations ------------------------------------------------------------------


def _object_classes() -> list[type[Node]]:
    """Every object class defined by kinemo (components declare props with `k.Prop`)."""
    found: list[type[Node]] = []
    pending: list[type[Node]] = [Node]
    while pending:
        cls = pending.pop()
        found.append(cls)
        pending.extend(cls.__subclasses__())
    return [c for c in found if c.__module__.startswith("kinemo.") and not issubclass(c, Component)]


def _declared_props(cls: type) -> dict[str, str]:
    """`name: PropAccessor[T]` declared in the class's own `if TYPE_CHECKING:` blocks."""
    try:
        source = textwrap.dedent(inspect.getsource(cls))
    except (OSError, TypeError):
        return {}
    class_def = ast.parse(source).body[0]
    assert isinstance(class_def, ast.ClassDef)
    declared: dict[str, str] = {}
    for statement in class_def.body:
        if isinstance(statement, ast.If) and isinstance(statement.test, ast.Name) and statement.test.id == "TYPE_CHECKING":
            for item in statement.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    declared[item.target.id] = ast.unparse(item.annotation)
    return declared


@pytest.mark.parametrize("cls", _object_classes(), ids=lambda c: c.__qualname__)
def test_object_props_are_declared_for_the_type_checker(cls: type[Node]) -> None:
    declared: dict[str, str] = {}
    for base in reversed(cls.__mro__):
        declared.update(_declared_props(base))
    for name, spec in cls._all_props.items():
        shadowed = any(name in vars(base) for base in cls.__mro__)  # a method of the same name wins
        if name.startswith("_") or shadowed:
            continue
        assert name in declared, f"{cls.__qualname__}.{name} is not declared under TYPE_CHECKING"
        expected = f"PropAccessor[{KIND_TYPES[spec.kind]}]"
        assert declared[name] == expected, f"{cls.__qualname__}.{name}: declared {declared[name]}, kind {spec.kind!r} is {expected}"
