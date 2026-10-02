"""`diagnostics.md`: every code of the diagnostics catalog, grouped by range."""

from __future__ import annotations

import re

from .. import reference
from .writer import code, code_block, heading, link, page, slug, table

GENERAL_RANGE = ("K00xx", "General")


def _ranges() -> list[tuple[str, str, str]]:
    """(two-digit range, label, area): `("02", "K02xx / W02xx", "Animations, ...")`."""
    out = []
    for label, area in (GENERAL_RANGE, *reference.DIAGNOSTIC_RANGES):
        digits = re.search(r"\d\d", label)
        if digits is not None:
            out.append((digits.group(0), label, area))
    return out


def _severity(code_name: str) -> str:
    return "error" if code_name.startswith("K") else "warning (lint)"


def diagnostics_page() -> str:
    from ...diagnostics import CATALOG

    groups: dict[str, list[str]] = {}
    for name in sorted(CATALOG, key=lambda c: (c[1:], c)):
        groups.setdefault(name[1:3], []).append(name)
    ranges = [r for r in _ranges() if r[0] in groups]
    known = {r[0] for r in ranges}
    ranges += [(digits, f"{digits}xx", "Other") for digits in sorted(groups) if digits not in known]

    body = [
        "Every problem kinemo reports has a stable code: `K` codes are errors, `W` codes are lints "
        "(warnings; `kinemo check --strict` treats them as errors). Codes never change meaning and are "
        "never reused. `kinemo explain <code>` prints the same explanation in the terminal and "
        "`kinemo check --fix` applies the safe fixes. A lint can be allowed on one line with "
        "`# kinemo: allow W1002` or for the whole project in `kinemo.toml` "
        f"({link('`[lints] allow`', 'configuration.md#keys')}).",
        "",
        *table(
            ("Range", "Area", "Codes"),
            [(link(label, f"#range-{digits}"), area, str(len(groups[digits]))) for digits, label, area in ranges],
        ),
    ]
    for digits, label, area in ranges:
        body += heading(2, f"{label}: {area}", f"range-{digits}")
        body += table(
            ("Code", "Severity", "Title"),
            [(link(code(n), f"#{slug(n)}"), _severity(n), CATALOG[n].title) for n in groups[digits]],
        )
        for name in groups[digits]:
            item = CATALOG[name]
            body += heading(3, f"{name}: {item.title}", slug(name))
            body += [f"*{_severity(name).capitalize()}.* {item.explanation}", ""]
            if item.example:
                body += ["Example that triggers it:", "", *code_block(item.example)]
            if item.fix:
                body += ["Fix:", "", *code_block(item.fix)]
    return page("Diagnostics", "Error and lint codes reported by `kinemo check`, the preview and the build.", body)
