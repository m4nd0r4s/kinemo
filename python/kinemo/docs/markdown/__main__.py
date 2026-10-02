"""`python -m kinemo.docs.markdown <out_dir>`: write the Markdown API reference."""

from __future__ import annotations

import argparse

from . import write


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m kinemo.docs.markdown", description=__doc__)
    parser.add_argument("out_dir", help="directory for the pages (the repository uses docs/reference)")
    args = parser.parse_args(argv)
    for path in write(args.out_dir):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
