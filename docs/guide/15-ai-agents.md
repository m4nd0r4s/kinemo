# Using kinemo with AI agents

kinemo is designed so that a model can write a correct scene within a couple of `check`
iterations, without needing to look at the video. Five things make that work:

1. **A small, regular API.** One name per concept, verbs in `k.`, state changes through
   `.to()`. The whole public surface fits in [`llms.txt`](../llms.txt).
2. **Errors that teach.** Every diagnostic has a stable code and, whenever possible, the fix
   as code. An agent does not need to understand the architecture; it applies the fix.
3. **Manim translation.** Models have seen a lot of Manim code. kinemo recognizes Manim
   names and answers with the kinemo form (`K11xx`).
4. **Seeing without vision.** `check --json` gives the timeline and the lints, including
   visual ones (safe area, overlap, contrast, text size). `inspect --json` gives positions,
   sizes and where each value came from.
5. **Native tools.** `kinemo mcp` exposes `check`, `inspect`, `snap`, `docs` and `explain`
   as MCP tools, always in strict mode.

This guide is for people setting up an agent, and for agents themselves.

## The agent loop

1. **Read** `llms.txt`, or call `kinemo docs <symbol>` for the symbols you will use.
2. **Write** the scene.
3. **Check**: `kinemo check scene.py --json --strict`. If there are diagnostics, apply the
   fixes (or run `--fix`) and repeat.
4. **Inspect** the key instants, usually the end of each `s.play` (read them from the
   timeline): `kinemo inspect scene.py --at <t> --json`. Confirm positions and sizes.
5. **Optionally snap**: `kinemo snap scene.py --at 0,2.5,end`, for a visual review by a
   model with vision.
6. **Render**: `kinemo render scene.py`.

Strict mode matters. Warnings include the visual lints (`W1001` outside the safe area,
`W1002` text over text, `W1003` low contrast, `W1004` small text), which are exactly the
mistakes a person would notice in the video and a model without vision would not.

## `llms.txt`

`docs/llms.txt` is the reference written for models: the seven rules, the recommended loop,
the conventions, and every public symbol with its signature, a summary and one canonical
example. Every example passes `kinemo check --strict`. It also contains the diagnostic code
list and the Manim → kinemo table. It is generated from the code at each release
(`python -m kinemo.docs.llms`), so it always matches the installed version.

It shows only the canonical form of each thing. That is deliberate: contradictory examples
are the main cause of mixed code. Point your agent at it, for example from the project's
`CLAUDE.md` or `AGENTS.md`:

```markdown
This project uses kinemo for animations. Before writing a scene, read docs/llms.txt.
After every edit, run `kinemo check <file> --json --strict` and apply the fixes until it
passes. Never use Manim names. Use `kinemo docs <symbol>` when unsure about a signature.
```

For one symbol at a time, `kinemo docs` returns the same entry as `llms.txt`:

```bash
kinemo docs k.when --json   # {symbol, canonical, area, signature, summary, example, methods, related}
```

## `kinemo check --json`

The payload has one entry per scene in the file:

```json
{
  "file": "edge.py",
  "scenes": [
    {
      "name": "edge",
      "ok": true,
      "duration": 1.5,
      "timeline": [
        {"start": 0.0, "end": 1.0, "label": "write(title)", "file": "/abs/path/edge.py", "line": 7}
      ],
      "diagnostics": [
        {
          "code": "W1001",
          "level": "warning",
          "message": "title leaves the safe area (top, 0.4 u)",
          "spans": [{"file": "/abs/path/edge.py", "line": 6, "col": 0}],
          "time": 1.0,
          "objects": ["title"],
          "fixes": [
            {
              "description": "clamp the constraint to the safe area",
              "code": "title = k.Text(\"A long title near the top\", size=0.6).place(at=\"top\", margin=0.1, clamp=True)",
              "edits": [
                {
                  "file": "/abs/path/edge.py",
                  "line": 6,
                  "replacement": "    title = k.Text(\"A long title near the top\", size=0.6).place(at=\"top\", margin=0.1, clamp=True)"
                }
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

| Field | Meaning |
| --- | --- |
| `scenes[].ok` | `true` when the scene built **without errors**. Warnings do not change it, even with `--strict`. |
| `scenes[].duration` | Total duration in seconds (tail included), or `null` when the build failed |
| `scenes[].timeline` | Every scheduled animation, in time order, with the line that scheduled it |
| `diagnostics[].code` | Stable code (`K` errors, `W` warnings). Codes never change meaning. |
| `diagnostics[].level` | `error`, `warning` or `hint` |
| `diagnostics[].spans` | Where: the first span is the offending line; others are related lines (a constraint, an exit) |
| `diagnostics[].time` | Instant on the timeline, when the problem has one |
| `diagnostics[].objects` | Labels of the objects involved |
| `diagnostics[].fixes` | Zero or more fixes. `code` is the replacement as text; `edits` are exact whole-line replacements (1-based `line`, `replacement` including indentation). |

Rules for an agent:

- **Decide success with the exit code**: `kinemo check --json --strict` exits with 1 if
  there is any error or warning. `scenes[].ok` alone does not account for `--strict`.
- **Apply `edits` literally** when a fix has them. A fix with `code` but no `edits` shows the
  new code without knowing exactly where it goes, and a fix with neither is advice
  ("increase the timeout or check the condition").
- **When there are several fixes**, they are alternatives. Pick one.
- **`kinemo check --fix`** applies the fix of each diagnostic that has exactly one fix with
  edits, then checks again.
- **When the file itself fails to load** (a syntax error, an exception at import time), the
  payload is `{"file": ..., "scenes": [], "diagnostics": [...]}`, usually with `K0001`.

`kinemo explain <code>` returns the long explanation of any code.

## `kinemo inspect --json`

```json
{
  "scene": "derivative",
  "t": 5.0,
  "objects": [
    {
      "id": 66,
      "label": "dot",
      "name": "dot",
      "kind": "dot",
      "parent": null,
      "present": true,
      "position": [-2.11, 0.04],
      "bbox": [-2.21, -0.06, -2.01, 0.14],
      "position_source": {"kind": "place", "placement": {"at_point": {"op": "to_world", "...": "..."}, "side": null, "target": null, "gap": null}},
      "props": {"fill": {"Color": [0.91, 0.39, 0.35, 1.0]}, "opacity": {"Float": 1.0}, "...": "..."},
      "prop_sources": {"fill": {"kind": "initial", "span": {"file": "/abs/path/derivative.py", "line": 17, "col": 0}}, "...": "..."},
      "span": {"file": "/abs/path/derivative.py", "line": 17, "col": 0}
    }
  ]
}
```

| Field | Meaning |
| --- | --- |
| `label` | How diagnostics and `check` refer to the object: variable name, `row[2]`, `txt["never"]`, or `kind#id` |
| `position` | Position in the parent's coordinates. The frame is 16 × 9 units, origin at the center, y up. |
| `bbox` | `[x0, y0, x1, y1]` in world coordinates |
| `present` | Whether the object is in the scene at `t` (with `--all`, absent objects are listed too) |
| `position_source.kind` | `place` (a constraint, with its `placement`), `container` (a `Row`/`Grid`...), or `free` (plain `x`/`y`) |
| `props` | Every prop at `t`, tagged by type: `{"Float": 1.0}`, `{"Vec2": [x, y]}`, `{"Color": [r, g, b, a]}` (0 to 1), `{"Str": "..."}`, `{"Bool": true}`, `{"List": [...]}` |
| `prop_sources` | Where each prop's value comes from: `initial` (constructor), `animation` or `binding`, with the source line |
| `drawn_glyphs` | Only on the runs that draw a text's glyphs: the indices of the glyphs this run draws at `t`. Each glyph of a text is drawn by exactly one run. |

Typical checks: two `bbox` overlapping, a `bbox` outside `[-8, -4.5, 8, 4.5]`, a label that
is not where the script intended. `--at` accepts seconds, a mark name or `end`.

## The MCP server

`kinemo mcp` runs a [Model Context Protocol](https://modelcontextprotocol.io) server over
stdio. Every tool runs in strict mode, so warnings are failures.

| Tool | Arguments | Returns |
| --- | --- | --- |
| `check` | `file`, optional `scene`, `params` | The `check --json` payload plus top-level `ok` and `strict` |
| `inspect` | `file`, `at`, optional `scene`, `params`, `all` | One `inspect` payload per scene, with its diagnostics |
| `snap` | `file`, `at` (`"0,2.5,end"` or a list), optional `quality`, `scene`, `params` | PNG images plus a JSON index of the frames |
| `docs` | `symbol` (`"k.morph"`, `"ax.plot"`) | The documentation entry; unknown symbols return suggestions |
| `explain` | `code` (`"K0401"`) | The long explanation |

Results carry the JSON both as `structuredContent` and as text. A failing check (or a file
that does not load) is returned as a tool result with `isError: true`, not as a protocol
error, so the agent sees the diagnostics. Unlike the CLI's `scenes[].ok`, the top-level
`ok` of the MCP tools does account for strict mode. Anything the scene prints goes to
stderr, never to the protocol stream.

`file` is resolved relative to the **server's working directory**. Pass absolute paths, or
start the server from the project root.

### Claude Code

```bash
# for you only, in this project
claude mcp add kinemo -- kinemo mcp

# shared with the team: writes .mcp.json at the project root
claude mcp add --scope project kinemo -- kinemo mcp
```

If `kinemo` is installed in a virtual environment, use the full path to the executable, for
example `claude mcp add kinemo -- /path/to/project/.venv/bin/kinemo mcp`. The resulting
`.mcp.json`:

```json
{
  "mcpServers": {
    "kinemo": {
      "command": "/path/to/project/.venv/bin/kinemo",
      "args": ["mcp"]
    }
  }
}
```

Check the connection with `claude mcp list`, or `/mcp` inside a session. The server sends
the agent loop as its instructions when the client connects.

### Other clients

Most clients take the same command and arguments:

- **Claude Desktop, Cursor, Windsurf** and similar: an `mcpServers` entry like the one above,
  in the client's MCP configuration file.
- **VS Code** (`.vscode/mcp.json`):

  ```json
  {
    "servers": {
      "kinemo": { "type": "stdio", "command": "/path/to/project/.venv/bin/kinemo", "args": ["mcp"] }
    }
  }
  ```

- **Any client that runs a command**: `kinemo mcp` (stdio, newline-delimited JSON-RPC,
  protocol versions 2025-06-18, 2025-03-26 and 2024-11-05).

## Manim translation (K11xx)

Models trained on Manim will write `Create`, `self.play` and `.animate`. When the Manim name
is reached through `k.` or on a kinemo object, kinemo stops with a `K11xx` error that gives
the kinemo form:

```
K1101 error: 'Create' is a Manim name. In kinemo: k.draw(obj)
  --> scene.py:6           s.play(k.Create(c))
  fix: use
         k.draw(obj)
```

| Code | Triggered by | kinemo form |
| --- | --- | --- |
| `K1101` | `k.Create`, `k.Write`, `k.FadeIn`, `k.Transform`, `k.ReplacementTransform`, `k.TransformMatchingTex`, `k.GrowFromCenter`, `k.Indicate`, `k.MoveAlongPath`, `k.Succession`, `k.LaggedStart`, `k.VGroup`, `k.MathTex`, `k.Tex`, ... | `k.draw`, `k.write`, `k.fade_in`, `k.morph`, `k.grow`, `k.indicate`, `k.follow`, `k.seq`, `k.stagger`, `k.Group`, `k.Math`, `k.Text` |
| `K1102` | `obj.animate`, `obj.shift`, `obj.move_to`, `obj.set_color`, `obj.set_fill` | `s.play(obj.to(...))`, `obj.set(...)` |
| `K1103` | `k.ThreeDScene`, `k.MovingCameraScene` | `@k.scene(camera="3d")` (3D is planned after 1.0) |
| `K1104` | `k.ValueTracker` | `k.signal(0)` |
| `K1105` | `obj.add_updater` | Pass a signal or a lambda to the prop: `obj.set(x=other.x)` |
| `K1106` | `k.UP`, `k.DOWN`, `k.LEFT`, `k.RIGHT`, `k.ORIGIN`, `k.UL`, ..., `obj.next_to`, `obj.to_edge`, `obj.to_corner`, `obj.arrange`, `obj.get_center`, `obj.get_x` | `.place(above=...)`, `.place(at="top")`, `k.Row`, `obj.center.now`, `obj.x.now` |

Some Manim patterns are not translated, because they never reach kinemo:

- `from manim import *` is a plain import error (`K0001`, "No module named 'manim'").
- A class-based scene (`class S(k.Scene): def construct(self): ...`) is not a scene, so
  `check` reports "no scenes (@k.scene)". `self.play` inside it is never run.

The full table is at the end of `llms.txt`. The essentials:

| Manim | kinemo |
| --- | --- |
| `class S(Scene): def construct(self)` | `@k.scene def s(s: k.Scene)` |
| `self.play(Create(x))` | `s.play(k.draw(x))` |
| `self.play(x.animate.shift(UP))` | `s.play(x.to(y=x.y.now + 1))` |
| `x.next_to(y, DOWN)` | `x.place(below=y)` |
| `VGroup(a, b).arrange(RIGHT)` | `k.Row(a, b)` |
| `ValueTracker(0)` + `add_updater` | `k.signal(0)` + a lambda or signal in the prop |
| `MathTex(r"...")` | `k.Math(r"...")` |
| `self.wait()` | `s.wait()` |

## A worked iteration

An agent writes:

```python
title = k.Text("Results").place(at="top")
chart = k.BarChart(data, x="country", y="GWh").place(below=title)
s.play(k.write(title), k.Create(chart))
```

The build stops at the first error, in source order. The first `check --json --strict`
returns `K1202`, "the table has no column 'GWh'", with the fix "available columns: country,
gwh". After that change, the next check reaches the third line and returns `K1101`, "'Create'
is a Manim name. In kinemo: k.draw(obj)". After that one, the scene passes. Lints such as
`W1001` come with exact edits that `--fix` can apply directly. Three iterations, no
rendering, and the tool spelled out every step.

## Common mistakes

> | Diagnostic | What happened | Fix |
> | --- | --- | --- |
> | `K1101`–`K1106` | Manim names and methods. | Apply the translation in the fix. |
> | `K0001`, or "no scenes" | `from manim import *` (an import error), or a class-based scene that `check` does not recognize. | Start from `import kinemo as k` and `@k.scene def name(s: k.Scene):`. |
> | false success | The agent read `scenes[].ok` and ignored warnings. | Use the exit code of `check --strict`, or the MCP tool's top-level `ok`. |
> | file not found (MCP) | A relative `file` resolved against the server's working directory. | Pass absolute paths, or start the server in the project root. |
> | `K0301` / `K0302` | `x()` in the scene body, or `x.now` inside a lambda. | `x.now` while building; `x()` inside lambdas, `.map` and `k.computed`. |
> | `K0310` | `math.sin`, `if` or `min()` inside a traced function. | `k.sin`, `k.where`, `k.min`; `k.python(fn)` as the explicit escape hatch. |
> | `K0401` | Animating `x`/`y` of an object placed with `.place`. | `obj.to_place(...)`, or `obj.to(x=..., unpin=True)`. |
> | `W1001`, `W1002` | Layout by coordinates instead of constraints. | `.place(below=...)`, `k.Row`, `k.Column`, `.fit(s.frame.safe)`. |

See also: [Tooling](14-tooling.md), [Diagnostics reference](../reference/diagnostics.md),
[Command line reference](../reference/cli.md#mcp), [`llms.txt`](../llms.txt).
