"""`configuration.md`: `kinemo.toml` keys (`kinemo/project.py`), `@k.scene` options
(`scene/decorator.py`, `scene/config.py`), size presets and quality presets."""

from __future__ import annotations

import dataclasses
import inspect
import typing

from .typed_signatures import clean_annotation, default_text
from .writer import code, code_block, heading, link, page, table

#: What each `@k.scene` option does.
SCENE_OPTIONS = {
    "size": "Output size: a preset name (`\"1080p\"`, `\"4k\"`, `\"vertical\"`, ...) or `(width, height)` in pixels.",
    "fps": "Frames per second of the final render.",
    "background": "Background color; `None` uses the theme's `bg`.",
    "seed": "Seed for `random` and `numpy.random` during the build, so scenes are reproducible.",
    "tail": "Seconds added after the last animation ends.",
    "theme": "A `k.Theme` or the name of one in `k.themes` (`\"dark\"`, `\"light\"`, `\"blueprint\"`).",
    "camera": "`\"2d\"` or `\"3d\"`.",
    "params": "Scene parameters (`k.Int`, `k.Float`, `k.Bool`, `k.Choice`, `k.Str`), passed to the function by name.",
    "name": "Scene name used by `--scene`; defaults to the function name.",
}

#: Options that only the decorator accepts (not `kinemo.toml [scene]`).
DECORATOR_ONLY = ("params", "name")

#: Draft quality limits, mirrored from the renderer (`crates/kinemo-render/src/renderer.rs`).
DRAFT_SHORT_SIDE = 540
DRAFT_MAX_FPS = 30.0


def _scene_overload() -> inspect.Signature:
    from ...scene.decorator import scene

    variants = [inspect.signature(v) for v in typing.get_overloads(scene)]
    return max(variants, key=lambda s: len(s.parameters))


def _project_defaults() -> dict[str, object]:
    from ...project import ProjectConfig

    return {f.name: f.default for f in dataclasses.fields(ProjectConfig) if f.default is not dataclasses.MISSING}


def _toml_rows() -> list[tuple[str, str, str, str]]:
    defaults = _project_defaults()
    scene = _scene_overload().parameters
    rows = [
        (code(f"[scene] {name}"), code(clean_annotation(p.annotation)), code(default_text(p.default)), SCENE_OPTIONS[name])
        for name, p in scene.items()
        if name not in DECORATOR_ONLY
    ]
    rows += [
        (code("[render] *"), "table", code("{}"),
         "Read into `ProjectConfig.render`; the CLI does not use it yet. The output directory is set with "
         "`--out` (default `out`)."),
        (code("[lints] allow"), code("list[str]"), code("[]"),
         "Lint codes allowed in the whole project (see [diagnostics](diagnostics.md))."),
        (code("[tts] provider"), code("str"), code(default_text(defaults["tts_provider"])),
         "Text-to-speech provider for `s.voice`. Without one, `s.voice` is silent with an estimated "
         "duration and lint W1401 is reported. `\"command\"` runs `[tts] command`."),
        (code("[tts] command"), code("list[str]"), code("[]"),
         "Command of the `command` provider, run from the project root for each line: `{text_file}`, "
         "`{out}` and `{voice}` are replaced. With `{lines_file}` instead (a JSON list of "
         "`{text, out, voice}`), it runs once for every line. A string is split like a shell command."),
        (code("[tts] on_build"), code("str"), code("None"),
         "`\"synthesize\"`: a build makes the audio of lines that have none; `\"estimate\"`: they stay "
         "estimated (W1405) until `kinemo voice` or `kinemo render` makes them. Unset: `estimate` for the "
         "`command` provider, `synthesize` for the others. `kinemo check` always estimates."),
        (code("[tts] wpm"), code("float"), code(default_text(defaults["tts_wpm"])),
         "Speaking rate (words per minute) of the silent estimate used when a line has no audio."),
        (code("[audio] loudness"), code("float"), code(default_text(defaults["audio_loudness"])),
         "Integrated loudness of rendered audio, in LUFS (e.g. `-16`). Without it, the mix keeps its level."),
        (code("[audio] trim_silence"), code("bool"), code(default_text(defaults["audio_trim_silence"])),
         "Cut the silence around each narration line when it is measured."),
        (code("[align] model"), code("str"), code(default_text(defaults["align_model"])),
         "Speech model that aligns words to narration audio, with `pip install \"kinemo[align]\"`."),
        (code("[cache] dir"), code("str"), code(default_text(defaults["cache_dir"])),
         "Cache directory (generated audio, ...), relative to the project root."),
        (code("[editor] command"), code("str"), code(default_text(defaults["editor"])),
         "Editor the preview opens when an object is clicked (`vscode`, `idea` or a command)."),
        (code("[python] workers_threshold"), code("float"), code(default_text(defaults["python_workers_threshold"])),
         "Seconds of `k.python` computation above which a worker pool is used."),
    ]
    return rows


def _size_rows() -> list[tuple[str, ...]]:
    from ...scene.config import SIZES, SceneConfig

    rows = []
    for name, (width, height) in SIZES.items():
        units_w, units_h = SceneConfig(name="size", size=(width, height)).frame_units
        draft_w, draft_h = _draft_size(width, height)
        rows.append((code(f'"{name}"'), f"{width} × {height}", f"{units_w:g} × {units_h:g}", f"{draft_w} × {draft_h}"))
    return rows


def _even(value: int) -> int:
    return value + (value & 1)


def _draft_size(width: int, height: int) -> tuple[int, int]:
    scale = min(DRAFT_SHORT_SIDE / min(width, height), 1.0)
    return _even(round(width * scale)), _even(round(height * scale))


def configuration_page() -> str:
    from ...cli.new import TOML
    from ...scene.config import SHORT_SIDE_UNITS

    scene_rows = [
        (code(name), code(clean_annotation(p.annotation)), code(default_text(p.default)), SCENE_OPTIONS[name],
         "decorator only" if name in DECORATOR_ONLY else "also `[scene]`")
        for name, p in _scene_overload().parameters.items()
    ]
    body = [
        "Precedence, from strongest to weakest: command-line flags, the `@k.scene` decorator, the "
        "`[scene]` table of `kinemo.toml`, built-in defaults.",
        "",
        *heading(2, "`kinemo.toml`", "kinemo-toml"),
        "Found by walking up from the current directory; the directory that contains it is the project "
        f"root. {link('`kinemo new`', 'cli.md#new')} writes this one:",
        "",
        *code_block(TOML, "toml"),
        *heading(3, "Keys", "keys"),
        *table(("Key", "Type", "Default", "Effect"), _toml_rows()),
        *heading(2, "`@k.scene` options", "scene-options"),
        *code_block('@k.scene(size="vertical", fps=30, tail=1.0, theme="light")\ndef intro(s: k.Scene): ...'),
        *table(("Option", "Type", "Default", "Effect", "Where"), scene_rows),
        f"See {link('`k.scene`', 'scene.md#k-scene')} and {link('`k.SceneDef`', 'scene.md#k-scenedef')}.",
        "",
        *heading(2, "Sizes", "sizes"),
        f"The frame always has {SHORT_SIDE_UNITS:g} units on its shorter side; the longer side follows the "
        "aspect ratio. The origin is the center and y points up.",
        "",
        *table(("Preset", "Pixels", "Frame units", "Draft pixels"), _size_rows()),
        "Any `(width, height)` tuple is also accepted.",
        "",
        *heading(2, "Quality presets", "quality"),
        *table(
            ("Preset", "Resolution", "Frame rate", "Used by"),
            [
                (code("draft"), f"shorter side scaled down to {DRAFT_SHORT_SIDE} px (never up), even sizes",
                 f"the scene's fps, at most {DRAFT_MAX_FPS:g}", "`kinemo dev`, `kinemo snap` (default)"),
                (code("final"), "the scene's size", "the scene's fps", "`kinemo render` (default)"),
            ],
        ),
        "Choose with `--quality draft|final` on `kinemo snap` and `kinemo render`.",
        "",
    ]
    return page("Configuration", "Project and scene settings.", body)
