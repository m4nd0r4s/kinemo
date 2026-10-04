"""`cli.md`: every `kinemo` subcommand, read from the argparse parser of `kinemo.cli.main`."""

from __future__ import annotations

import argparse

from .writer import code, code_block, heading, link, page, table

#: Usage examples per subcommand (the arguments themselves come from the parser).
EXAMPLES: dict[str, tuple[str, ...]] = {
    "new": ("kinemo new my-video", "cd my-video && kinemo check scene.py && kinemo render scene.py"),
    "dev": ("kinemo dev scene.py", "kinemo dev scene.py --scene intro --debug layout,safe --port 8000"),
    "check": (
        "kinemo check scene.py",
        "kinemo check scene.py --json --strict",
        "kinemo check scene.py --fix",
        "kinemo check scene.py --scene intro --param n=5",
    ),
    "inspect": ("kinemo inspect scene.py --at 2.5", "kinemo inspect scene.py --at end --json --all"),
    "snap": ("kinemo snap scene.py --at 0,2.5,end", "kinemo snap scene.py --at intro_done --quality final --out shots"),
    "render": (
        "kinemo render scene.py",
        "kinemo render scene.py --format gif --quality draft",
        "kinemo render scene.py --format png --at end --transparent",
        "kinemo render scene.py --format slides",
    ),
    "mcp": ("kinemo mcp",),
    "docs": ("kinemo docs", "kinemo docs k.morph", "kinemo docs s.play --json", "kinemo docs --check"),
    "upgrade": ("kinemo upgrade scene.py --check", "kinemo upgrade scenes/*.py"),
    "explain": ("kinemo explain K0101",),
}


def _subcommands(parser: argparse.ArgumentParser) -> list[tuple[str, str, argparse.ArgumentParser]]:
    """(name, help, parser) of each subcommand, in registration order."""
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            helps = {choice.dest: choice.help or "" for choice in action._choices_actions}
            return [(name, helps.get(name, ""), sub) for name, sub in action.choices.items()]
    return []


def _metavar(action: argparse.Action, fallback: str) -> str:
    metavar = action.metavar
    if isinstance(metavar, tuple):
        return " ".join(metavar)
    return metavar or fallback


def _argument_name(action: argparse.Action) -> str:
    if action.option_strings:
        name = ", ".join(action.option_strings)
        if action.nargs != 0 and not isinstance(action, argparse._StoreConstAction):
            name += f" {_metavar(action, action.dest.upper())}"
        return name
    return _metavar(action, action.dest)


def _argument_details(action: argparse.Action) -> tuple[str, str, str]:
    """(type or choices, default, notes) of one argument."""
    if action.choices:
        kind = " \\| ".join(code(str(c)) for c in action.choices)
    elif action.nargs == 0:
        kind = "flag"
    else:
        kind = getattr(action.type, "__name__", "str") if action.type else "str"
    notes = []
    if not action.option_strings:
        notes.append({"?": "optional", "+": "one or more", "*": "zero or more"}.get(str(action.nargs), "required"))
    if isinstance(action, argparse._AppendAction):
        notes.append("repeatable")
    has_default = action.default not in (None, False, "", argparse.SUPPRESS) and action.nargs != 0
    return kind, code(str(action.default)) if has_default else "", ", ".join(notes)


def _arguments_table(sub: argparse.ArgumentParser) -> list[str]:
    rows = []
    for action in sub._actions:
        if isinstance(action, argparse._HelpAction):
            continue
        kind, default, notes = _argument_details(action)
        # argparse help escapes % as %%.
        description = (action.help or "").replace("%%", "%") + (f" ({notes})" if notes else "")
        rows.append((code(_argument_name(action)), kind, default, description.strip()))
    if not rows:
        return ["Takes no arguments.", ""]
    return table(("Argument", "Type", "Default", "Description"), rows)


def _usage(sub: argparse.ArgumentParser) -> str:
    text = " ".join(sub.format_usage().split())
    return text.removeprefix("usage: ")


def cli_page() -> str:
    from ...cli.main import parser as build_parser

    root = build_parser()
    commands = _subcommands(root)
    body = [
        f"{root.description} Every subcommand takes `-h` / `--help`. Exit codes: 0 when everything is "
        "fine, non-zero when there are errors (or warnings with `--strict`).",
        "",
        *table(("Command", "Summary"), [(link(code(f"kinemo {n}"), f"#{n}"), h) for n, h, _ in commands]),
        "Scene commands (`dev`, `check`, `inspect`, `snap`, `render`) take the file, `--scene NAME` "
        "to pick one scene (default: all) and `--param NAME=VALUE` (repeatable) to set "
        f"{link('scene parameters', 'parameters.md')}. Settings precedence: CLI > `@k.scene` > "
        f"`kinemo.toml` > defaults ({link('configuration', 'configuration.md')}).",
        "",
    ]
    for name, help_text, sub in commands:
        body += heading(2, f"`kinemo {name}`", name)
        description = sub.description or help_text
        body += [description[:1].upper() + description[1:] + ("" if description.endswith(".") else "."), ""]
        body += code_block(_usage(sub), "text")
        body += _arguments_table(sub)
        examples = EXAMPLES.get(name, ())
        if examples:
            body += ["Examples:", "", *code_block("\n".join(examples), "sh")]
    return page("Command line", "The `kinemo` command, installed with the package.", body)
