"""`kinemo new <name>`: a project with kinemo.toml, an example scene and Pyright config."""

from __future__ import annotations

import argparse
import os

TOML = """# kinemo project configuration
[scene]
fps = 60
size = "1080p"
theme = "dark"

[render]
out = "out"

[lints]
allow = []
"""

SCENE = '''import kinemo as k


@k.scene
def intro(s: k.Scene):
    title = k.Text("{title}", size=0.8).place(at="center")
    s.play(k.write(title))
    s.play(title.to(color=k.BLUE))
    s.wait(1)
'''

PYRIGHT = """{
  "typeCheckingMode": "strict",
  "reportMissingTypeStubs": false
}
"""


def run(args: argparse.Namespace) -> int:
    root = os.path.abspath(args.name)
    if os.path.exists(root) and os.listdir(root):
        print(f"kinemo: {root} already exists and is not empty")
        return 1
    os.makedirs(root, exist_ok=True)
    files = {
        "kinemo.toml": TOML,
        "scene.py": SCENE.format(title=os.path.basename(root)),
        "pyrightconfig.json": PYRIGHT,
        ".gitignore": "out/\n",
    }
    for name, content in files.items():
        with open(os.path.join(root, name), "w", encoding="utf-8") as fh:
            fh.write(content)
    print(f"kinemo: project created in {root}")
    print(f"  cd {args.name} && kinemo check scene.py && kinemo render scene.py")
    return 0
