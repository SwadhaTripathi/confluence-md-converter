"""Detect diagram macros in Confluence storage XHTML and extract their source where possible.

A macro is "inline-source" when it carries the diagram text in <ac:plain-text-body> at
authoring time (mermaid, plantuml). Drawio and gliffy historically store the source in a
separate attachment — but our preprocess step (see preprocess.expand_drawio_macros) injects
a synthetic <ac:plain-text-body> after fetching and decoding the attachment, so by the time
the converter runs, drawio macros also look "inline" if extraction succeeded.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from bs4 import Tag


# Maps Confluence macro names to the language tag we emit in the fenced code block.
DIAGRAM_MACROS = {
    "mermaid": "mermaid",
    "mermaid-cloud": "mermaid",
    "plantuml": "plantuml",
    "plantumlrender": "plantuml",
    "drawio": "drawio",
    "drawio-board": "drawio",
    "gliffy": "gliffy",
}


@dataclass
class MacroSource:
    type: str        # "mermaid" | "plantuml" | "drawio" | "gliffy"
    source: str      # diagram source text; empty if not yet extracted
    inline: bool     # True if `source` is non-empty


def _macro_name(el: Tag) -> Optional[str]:
    """Return the macro name regardless of whether ':' was renamed to '_'."""
    return el.get("ac:name") or el.get("ac_name")


def get_macro_param(macro_el: Tag, name: str) -> str:
    """Return the value of <ac:parameter ac:name="name">…</ac:parameter>, or empty string."""
    for p in macro_el.find_all("ac_parameter"):
        if p.get("ac:name") == name or p.get("ac_name") == name:
            return p.get_text().strip()
    return ""


def extract_macro_source(macro_el: Tag) -> Optional[MacroSource]:
    name = _macro_name(macro_el)
    if not name:
        return None
    name = name.lower()
    if name not in DIAGRAM_MACROS:
        return None

    body = macro_el.find(["ac:plain-text-body", "ac_plain-text-body", "ac_plain_text_body"])
    source = (body.get_text() if body else "").strip()
    return MacroSource(type=DIAGRAM_MACROS[name], source=source, inline=bool(source))


def find_wrapping_macro(image_el: Tag) -> Optional[MacroSource]:
    """If an <ac:image> is rendered inside a diagram macro, return that macro's info."""
    for ancestor in image_el.parents:
        if not isinstance(ancestor, Tag):
            continue
        if ancestor.name in {"ac:structured-macro", "ac_structured-macro", "ac_structured_macro"}:
            return extract_macro_source(ancestor)
    return None
