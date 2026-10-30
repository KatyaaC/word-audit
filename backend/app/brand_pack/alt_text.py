"""Missing and weak alt-text detection."""
from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Literal

from .models import ImageRef

_FILENAME_LIKE = re.compile(
    r"(\.(jpe?g|png|gif|webp|svg|bmp)$)|^(img|dsc|image|photo|pic|screenshot)[\s_-]?\d+",
    re.IGNORECASE,
)
_GENERIC = {"image", "picture", "photo", "img", "graphic", "logo", "banner", "icon", "alt"}


class _ImgParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.images: list[ImageRef] = []

    def handle_starttag(self, tag, attrs):  # noqa: ANN001
        if tag.lower() != "img":
            return
        d = {k.lower(): v for k, v in attrs}
        decorative = d.get("role") in ("presentation", "none") or d.get("aria-hidden") == "true"
        self.images.append(ImageRef(src=d.get("src") or "", alt=d.get("alt"), decorative=decorative))


def images_from_html(html: str) -> list[ImageRef]:
    p = _ImgParser()
    p.feed(html)
    return p.images


AltIssue = Literal["missing", "empty", "weak"]


def check_image(img: ImageRef) -> AltIssue | None:
    if img.decorative:
        return None
    if img.alt is None:
        return "missing"
    alt = img.alt.strip()
    if alt == "":
        return "empty"
    if _FILENAME_LIKE.search(alt) or alt.lower() in _GENERIC:
        return "weak"
    return None
