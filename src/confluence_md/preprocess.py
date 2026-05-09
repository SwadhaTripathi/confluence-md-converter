"""Soup-level pre-processing that runs after parse_storage() but before markdown conversion.

- expand_drawio_macros: for each drawio macro, fetch the matching .drawio attachment,
  decode it, summarize, and inject a synthetic <ac:plain-text-body> so the existing
  inline-source-macro path picks it up and emits a fenced ```drawio code block.
- resolve_internal_links: for each <ac:link> with a <ri:page> target, look up the
  page's URL and tag the link element with `data-resolved-url` so the converter can
  emit `[text](url)` instead of just `text`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from bs4 import BeautifulSoup

from . import drawio
from .macros import _macro_name, get_macro_param


DrawioLoader = Callable[[str], Optional[Path]]
LinkResolver = Callable[[str, str], Optional[str]]  # (title, space_key) -> URL or None


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


def resolve_internal_links(soup: BeautifulSoup, *, link_resolver: LinkResolver) -> int:
    """Tag each resolvable <ac:link><ri:page/></ac:link> with `data-resolved-url`
    so the converter can render it as a real markdown link. Returns count resolved."""
    cache: dict[tuple[str, str], Optional[str]] = {}
    resolved = 0
    for link in soup.find_all(["ac_link", "ac:link"]):
        page_ref = link.find(["ri_page", "ri:page"])
        if page_ref is None:
            continue
        title = page_ref.get("ri:content-title") or page_ref.get("ri_content-title") or ""
        space_key = page_ref.get("ri:space-key") or page_ref.get("ri_space-key") or ""
        if not title:
            continue
        cache_key = (title, space_key)
        if cache_key not in cache:
            try:
                cache[cache_key] = link_resolver(title, space_key)
            except Exception:
                cache[cache_key] = None
        url = cache[cache_key]
        if url:
            link["data-resolved-url"] = url
            resolved += 1
    return resolved
