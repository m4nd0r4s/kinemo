"""The API pages of the reference: `README.md` (index by area) and one page per area."""

from __future__ import annotations

import kinemo

from .. import catalog, signatures
from . import class_details as details
from . import symbols as model
from .symbol_sections import PageState, symbol_section
from .writer import code, heading, link, page

#: One-line description of each area, shown in the index and at the top of its page.
AREA_INTROS = {
    "Scene": "Scenes, the timeline cursor and the blocks that shape time (`s.play`, `s.start`, `s.during`).",
    "Object state": "Changing objects: animated state changes (`.to()`), instant writes (`.set()`), copies.",
    "Verbs": "Entrance, exit and emphasis animations (`k.draw`, `k.fade_out`, `k.indicate`, `k.morph`).",
    "Composition": "Combining animations in sequence, in parallel and with a lag; reusable clips; easing.",
    "Objects": "Shapes, groups, images, SVG and mass objects (points, vector fields, stream lines).",
    "Text": "Text, LaTeX math and highlighted code, with addressable parts.",
    "Layout": "Placement by constraints (`.place`) and containers (`k.Row`, `k.Column`, `k.Grid`, `k.Stack`).",
    "Charts": "Axes, number lines, polar axes, plots and data charts.",
    "Reactive": "Signals, derived values and reactive collections.",
    "Native blocks": "Math blocks that run in the native core inside lambdas, `.map` and plots.",
    "Stateful systems": "Conditions, integration and simulations resolved before rendering.",
    "Events": "Event sources and handlers.",
    "Components": "Reusable components with props, outputs, events and context.",
    "Parameters": "Scene parameters for the interactive player and exports.",
    "Output": "Movies made of several scenes and the transitions between them.",
    "Theme and colors": "Themes, theme tokens and colors.",
    model.TOOLING_AREA: "Names for tools and type annotations rather than scene code.",
}

OTHER_PAGES = (
    ("diagnostics.md", "Diagnostics", "Every error and lint code, grouped by range, with explanations and fixes."),
    ("cli.md", "Command line", "Every `kinemo` subcommand with its arguments and examples."),
    ("configuration.md", "Configuration", "`kinemo.toml`, `@k.scene` options, sizes and quality presets."),
)


def _methods_of_area(area: str, file: str) -> list[str]:
    """Catalog entries of `area` that are methods, linked to the class page that documents them."""
    lines = []
    for entry in catalog.by_area().get(area, []):
        if entry.symbol.startswith("k."):
            continue
        shown = signatures.display_name(entry.symbol)
        lines.append(f"- {details.reference_link(entry.symbol, shown, file)}: {model.first_sentence(entry.summary)}")
    return lines


def area_page(area: str, items: list[model.Symbol]) -> str:
    file = model.page_file(area)
    state = PageState(file)
    body = ["**Contents:**", ""]
    body += [f"- {link(code(s.qualified), '#' + s.anchor)}: {model.summary_of(s)}" for s in items]
    body.append("")
    methods = _methods_of_area(area, file)
    if methods:
        body += ["**Methods in this area:**", "", *methods, ""]
    body += [f"Back to the {link('reference index', 'README.md')}.", ""]
    for symbol in items:
        body += symbol_section(symbol, state)
    return page(area, AREA_INTROS.get(area, ""), body)


def index_page() -> str:
    body = [
        f"kinemo {kinemo.__version__} (IR {kinemo.IR_VERSION}). Every name in `kinemo.__all__` and every "
        "public method of a public class, with signatures, parameters, props and canonical examples. "
        "Examples start with `import kinemo as k` and pass `kinemo check --strict`.",
        "",
        "Also: " + ", ".join(link(title, file) for file, title, _ in OTHER_PAGES) + ".",
        "",
    ]
    for area, items in model.symbols_by_area().items():
        file = model.page_file(area)
        body += heading(2, link(area, file))
        body += [AREA_INTROS.get(area, ""), ""]
        body += [f"- {link(code(s.qualified), f'{file}#{s.anchor}')}: {model.summary_of(s)}" for s in items]
        methods = _methods_of_area(area, "README.md")
        if methods:
            body += ["", "Methods:", "", *methods]
        body.append("")
    body += heading(2, "Other pages")
    body += [f"- {link(title, file)}: {description}" for file, title, description in OTHER_PAGES]
    return page("kinemo API reference", "", body)


def api_pages() -> dict[str, str]:
    pages = {"README.md": index_page()}
    for area, items in model.symbols_by_area().items():
        pages[model.page_file(area)] = area_page(area, items)
    return pages
