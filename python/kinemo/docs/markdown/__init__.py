"""Generate the Markdown API reference in `docs/reference/`.

    python -m kinemo.docs.markdown docs/reference

`generate()` returns `{file name: content}`; the test suite compares it with the committed
files, so the reference never drifts from the code."""

from __future__ import annotations

from .writer import write_pages


def generate() -> dict[str, str]:
    from .api_pages import api_pages
    from .cli_page import cli_page
    from .configuration_page import configuration_page
    from .diagnostics_page import diagnostics_page

    pages = api_pages()
    pages["diagnostics.md"] = diagnostics_page()
    pages["cli.md"] = cli_page()
    pages["configuration.md"] = configuration_page()
    return dict(sorted(pages.items()))


def write(out_dir: str) -> list[str]:
    return write_pages(generate(), out_dir)


__all__ = ["generate", "write"]
