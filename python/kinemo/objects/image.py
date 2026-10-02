"""`k.Image`: a raster image (PNG or JPEG) drawn by the renderer."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Unpack

from .._runtime.context import current_scene
from .media_paths import media_error, resolve_media_path
from .node import Node
from .props import PropSpec

if TYPE_CHECKING:
    import os

    from .keywords import TransformKeywords
    from .props import PropAccessor

#: Height in units when neither `width` nor `height` is given.
DEFAULT_IMAGE_HEIGHT = 3.0


class Image(Node):
    """`k.Image("photo.png", height=3)`: centered on its position, `w × h` units. Without
    a size it is 3 units tall; with one side the other keeps the file's aspect ratio.
    Morphs and layout treat it as its rectangle."""

    kind = "image"
    PROPS: ClassVar[dict[str, PropSpec]] = {
        "src": PropSpec("str", "", "step_end"),
        "w": PropSpec("float", 1.0),
        "h": PropSpec("float", 1.0),
    }

    if TYPE_CHECKING:
        src: PropAccessor[str]
        w: PropAccessor[float]
        h: PropAccessor[float]
        #: (width, height) of the file in pixels.
        pixel_size: tuple[int, int]

    def __init__(self, path: str | os.PathLike[str], width: float | None = None, height: float | None = None, **props: Unpack[TransformKeywords]) -> None:
        src = resolve_media_path(path, "k.Image")
        try:
            pixel_w, pixel_h = current_scene()._b.image_size(src)
        except ValueError as e:
            raise media_error("k.Image", src, str(e)) from None
        object.__setattr__(self, "pixel_size", (pixel_w, pixel_h))
        aspect = pixel_w / pixel_h
        if width is None and height is None:
            height = DEFAULT_IMAGE_HEIGHT
        if width is None:
            width = height * aspect
        elif height is None:
            height = width / aspect
        super().__init__(src=src, w=width, h=height, **props)
