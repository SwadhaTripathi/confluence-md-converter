"""Detect diagram macros in Confluence storage XHTML and extract their source where possible.

For mermaid / plantuml the source is inline in <ac:plain-text-body>, so we get full text.
For drawio / gliffy the diagram is stored as a separate attachment — we flag it so the image
fallback (the rendered PNG) plus OCR can do the work, and a future enhancement can download
and decode the .drawio / .gliffy attachment.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from bs4 import Tag


# Macro names that ship the full source as text inside the macro element.
INLINE_SOURCE_MACROS = {
    "mermaid": "mermaid",
    "mermaid-cloud": "mermaid",
    "plantuml": "plantuml",
    "plantumlrender": "plantuml",
}

# Macro names whose source lives in a separate attachment (not yet extracted).
ATTACHMENT_SOURCE_MACROS = {"drawio", "drawio-board", "gliffy"}


@dataclass
class MacroSource:
    type: str            # "mermaid" | "plantuml" | "drawio" | "gliffy"
    source: str          # actual diagram text, or empty if attachment-based
    inline: bool         # True if source was extracted; False means consult attachment


def _macro_name(el: Tag) -> Optional[str]:
    """Return the macro name regardless of whether ':' was renamed to '_'."""
    return el.get("ac:name") or el.get("ac_name")


def extract_macro_source(macro_el: Tag) -> Optional[MacroSource]:
    name = _macro_name(macro_el)
    if not name:
        return None
    name = name.lower()

    if name in INLINE_SOURCE_MACROS:
        body = macro_el.find(["ac:plain-text-body", "ac_plain-text-body", "ac_plain_text_body"])
        source = body.get_text() if body else ""
        return MacroSource(type=INLINE_SOURCE_MACROS[name], source=source.strip(), inline=True)

    if name in ATTACHMENT_SOURCE_MACROS:
        return MacroSource(type=name.split("-")[0], source="", inline=False)

    return None


def find_wrapping_macro(image_el: Tag) -> Optional[MacroSource]:
    """If an <ac:image> is rendered inside a diagram macro, return that macro's info."""
    for ancestor in image_el.parents:
        if not isinstance(ancestor, Tag):
            continue
        if ancestor.name in {"ac:structured-macro", "ac_structured-macro", "ac_structured_macro"}:
            return extract_macro_source(ancestor)
    return None
