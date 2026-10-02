"""`kinemo.testing`: test scenes with pytest without rendering video.

```python
import kinemo as k
from kinemo.testing import assert_snapshot, build, inspect

from scenes import hello


def test_title_ends_centered():
    built = build(hello)                     # raises SceneBuildError on errors
    assert built.duration == 3.5
    title = inspect(built, "end").object("title")
    assert title["position"] == [0.0, 0.0]


def test_title_looks_right():
    assert_snapshot(hello, 2.0)              # golden PNG in __snapshots__/ next to this file
```

Golden files are created on the first run; set `KINEMO_UPDATE_SNAPSHOTS=1` to rewrite them.
"""

from .building import BuiltScene, SceneBuildError, build
from .inspection import InspectReport, inspect
from .snapshots import SnapshotMismatch, assert_snapshot

__all__ = [
    "BuiltScene",
    "InspectReport",
    "SceneBuildError",
    "SnapshotMismatch",
    "assert_snapshot",
    "build",
    "inspect",
]
