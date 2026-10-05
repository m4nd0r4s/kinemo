"""`@k.scene`: turns a function into a buildable scene definition."""

from __future__ import annotations

import random
from dataclasses import replace
from typing import TYPE_CHECKING, Any, Callable, overload

from .._runtime.context import pop_scene, push_scene
from ..theme.tokens import Theme
from .config import SceneConfig, parse_size
from .scene import Scene

if TYPE_CHECKING:
    from ..params import Param
    from ..values.aliases import ColorLike

#: `def name(s: k.Scene, **params) -> None`: the function `@k.scene` decorates.
SceneFn = Callable[..., None]


class SceneDef:
    """A scene function plus its configuration. Building runs the function exactly once."""

    def __init__(self, fn: SceneFn, config: SceneConfig) -> None:
        self.fn = fn
        self.config = config
        self.name = config.name
        self.__doc__ = fn.__doc__
        self.__wrapped__ = fn

    def build(self, params: dict[str, object] | None = None, **overrides: object) -> Scene:
        """Run the build phase and return the scene with its finished timeline."""
        if "size" in overrides:
            overrides["size"] = parse_size(overrides["size"])
        config = replace(self.config, **overrides) if overrides else self.config
        s = Scene(config)
        state = random.getstate()
        np_state = _numpy_state()
        random.seed(config.seed)
        _seed_numpy(config.seed)
        token = push_scene(s)
        try:
            args = _param_signals(s, config, params or {})
            # Call stacks of statements stop at the scene function (see `user_stack`).
            s.__dict__["_scene_code"] = getattr(self.fn, "__code__", None)
            self.fn(s, **args)
            s._finish()
        finally:
            pop_scene(token)
            random.setstate(state)
            _restore_numpy(np_state)
        return s

    def __repr__(self) -> str:
        return f"<kinemo scene {self.name!r}>"


def _param_signals(s: Scene, config: SceneConfig, values: dict[str, Any]) -> dict[str, Any]:
    from ..params import param_signals

    return param_signals(s, config.params, values)


def _numpy_state() -> Any:
    try:
        import numpy as np  # noqa: F401
    except ImportError:
        return None
    import numpy as np

    return np.random.get_state()


def _seed_numpy(seed: int) -> None:
    try:
        import numpy as np
    except ImportError:
        return
    np.random.seed(seed)


def _restore_numpy(state: Any) -> None:
    if state is None:
        return
    import numpy as np

    np.random.set_state(state)


@overload
def scene(fn: SceneFn) -> SceneDef: ...


@overload
def scene(
    *,
    size: str | tuple[int, int] = "1080p",
    fps: float = 60,
    background: ColorLike | None = None,
    seed: int = 0,
    tail: float = 0.5,
    theme: Theme | str | None = None,
    camera: str = "2d",
    params: dict[str, Param] | None = None,
    name: str | None = None,
) -> Callable[[SceneFn], SceneDef]: ...


def scene(fn: SceneFn | None = None, **kwargs: Any) -> SceneDef | Callable[[SceneFn], SceneDef]:
    """Decorate `def name(s: k.Scene)` to make it a scene."""

    def wrap(f: SceneFn) -> SceneDef:
        from ..project import project_config
        from ..theme.tokens import DEFAULT, themes

        # Precedence: decorator > kinemo.toml [scene] > defaults (the CLI overrides at build).
        config = project_config()
        project = config.scene
        merged = {**project, **kwargs}
        theme = merged.get("theme") or DEFAULT
        if isinstance(theme, str):
            theme = getattr(themes, theme, DEFAULT)
        cfg = SceneConfig(
            name=kwargs.get("name") or f.__name__,
            size=parse_size(merged.get("size", "1080p")),
            fps=float(merged.get("fps", 60)),
            background=merged.get("background"),
            seed=int(merged.get("seed", 0)),
            tail=float(merged.get("tail", 0.5)),
            theme=theme,
            camera=merged.get("camera", "2d"),
            params=dict(kwargs.get("params") or {}),
            loudness=config.audio_loudness,
        )
        return SceneDef(f, cfg)

    if fn is not None:
        return wrap(fn)
    return wrap
