"""`kinemo upgrade`: apply codemods to scene files (`--check` only reports)."""

from __future__ import annotations

import argparse
import difflib
import os

from ..upgrade import upgrade_source


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("files", nargs="+")
    p.add_argument("--check", action="store_true", help="only show the diff; do not write")


def run(args: argparse.Namespace) -> int:
    changed = 0
    for path in args.files:
        with open(path, encoding="utf-8") as fh:
            old = fh.read()
        new, applied = upgrade_source(old)
        if not applied:
            continue
        changed += 1
        name = os.path.basename(path)
        if args.check:
            print("".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), name, name)))
        else:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(new)
            print(f"kinemo: {path}: {', '.join(applied)}")
    if not changed:
        print("kinemo: nothing to upgrade")
    return 1 if (args.check and changed) else 0
