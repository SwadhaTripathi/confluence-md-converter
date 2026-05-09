"""Soup-level pre-processing that runs after parse_storage() but before markdown conversion.

Currently only `expand_drawio_macros`: for each drawio macro, fetch the matching .drawio
attachment, decode it, summarize, and inject a synthetic <ac:plain-text-body> so the
existing inline-source-macro path picks it up and emits a fenced ```drawio code block.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from bs4 import BeautifulSoup

from . import drawio
from .macros import _macro_name, get_macro_param


DrawioLoader = Callable[[str], Optional[Path]]


def expand_drawio_macros(soup: BeautifulSoup, *, drawio_loader: DrawioLoader) -> int:
    """Mutate `soup` in place. Returns the number of drawio macros successfully expanded.

    drawio_loader: given a diagram name (without extension), returns the path to the
    decoded .drawio file on disk, or None if not available.
    """
    expanded = 0
    for macro in soup.find_all(["ac_structured-macro", "ac:structured-macro"]):
        name = (_macro_name(macro) or "").lower()
        if name not in {"drawio", "drawio-board"}:
            continue
        diagram_name = get_macro_param(macro, "diagramName")
        if not diagram_name:
            continue
        path = drawio_loader(diagram_name)
        if path is None or not path.exists():
            continue
        try:
            xml_text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        summary = drawio.summarize(xml_text)
        if not summary.strip():
            continue
        body = soup.new_tag("ac_plain-text-body")
        body.string = summary
        macro.append(body)
        expanded += 1
    return expanded
