"""Convert Confluence storage XHTML to markdown.

Storage format = XHTML with custom namespaced elements (<ac:image>, <ac:structured-macro>,
<ri:attachment>, etc.). We rename ':' to '_' in tag names so markdownify's method-dispatch
(which strips '-' to '_') can resolve handlers like `convert_ac_image`,
`convert_ac_structured_macro`, `convert_ri_attachment`.
"""
from __future__ import annotations

from typing import Callable

from bs4 import BeautifulSoup, Tag
from markdownify import MarkdownConverter

from .macros import extract_macro_source, get_macro_param


ImageProcessor = Callable[[Tag], str]


def _normalize_tag_names(soup: BeautifulSoup) -> None:
    for tag in soup.find_all():
        if ":" in tag.name:
            tag.name = tag.name.replace(":", "_")


class _Converter(MarkdownConverter):
    def __init__(self, image_processor: ImageProcessor, **opts):
        super().__init__(**opts)
        self._process_image = image_processor

    def convert_ac_image(self, el, text, *args, **kwargs):
        return self._process_image(el)

    def convert_ac_structured_macro(self, el, text, *args, **kwargs):
        name = (el.get("ac:name") or el.get("ac_name") or "").lower()

        macro = extract_macro_source(el)
        if macro and macro.inline:
            return f"\n\n```{macro.type}\n{macro.source}\n```\n\n"

        if name == "code":
            lang = get_macro_param(el,"language")
            body = el.find("ac_plain-text-body")
            code = body.get_text() if body else ""
            return f"\n\n```{lang}\n{code}\n```\n\n"

        if name in {"info", "warning", "note", "tip"}:
            return f"\n\n> **{name.capitalize()}:** {text.strip()}\n\n"

        if name == "expand":
            title = get_macro_param(el,"title")
            heading = f"**{title}**\n\n" if title else ""
            return f"\n\n{heading}{text}\n\n"

        if name in {"toc", "children", "pagetree"}:
            return ""

        return text

    def convert_ac_parameter(self, el, text, *args, **kwargs):
        return ""

    def convert_ac_plain_text_body(self, el, text, *args, **kwargs):
        return ""

    def convert_ac_rich_text_body(self, el, text, *args, **kwargs):
        return text

    def convert_ac_caption(self, el, text, *args, **kwargs):
        return ""

    def convert_ac_link(self, el, text, *args, **kwargs):
        body = el.find("ac_link-body")
        link_text = body.get_text(" ", strip=True) if body else (text or "")
        url = el.get("data-resolved-url")
        if url and link_text:
            return f"[{link_text}]({url})"
        return link_text

    def convert_ac_link_body(self, el, text, *args, **kwargs):
        return text

    def convert_ri_attachment(self, el, text, *args, **kwargs):
        return ""

    def convert_ri_url(self, el, text, *args, **kwargs):
        return ""

    def convert_ri_page(self, el, text, *args, **kwargs):
        return ""

    def convert_ri_user(self, el, text, *args, **kwargs):
        return ""

    def convert_u(self, el, text, *args, **kwargs):
        # Markdown has no native underline; <u> is widely supported by renderers
        # and indexed as plain text by RAG embedders.
        if not text or not text.strip():
            return text
        return f"<u>{text}</u>"


def parse_storage(storage_xhtml: str) -> BeautifulSoup:
    """Parse storage-format XHTML and normalize namespaced tag names so markdownify's
    method dispatch can find our `convert_ac_*` / `convert_ri_*` handlers."""
    soup = BeautifulSoup(storage_xhtml, "html.parser")
    _normalize_tag_names(soup)
    return soup


def soup_to_markdown(
    soup: BeautifulSoup,
    image_processor: ImageProcessor,
    *,
    page_title: str,
) -> str:
    converter = _Converter(image_processor=image_processor, heading_style="ATX", bullets="-")
    body_md = converter.convert_soup(soup).strip()
    return f"# {page_title}\n\n{body_md}\n"


def storage_to_markdown(
    storage_xhtml: str,
    image_processor: ImageProcessor,
    *,
    page_title: str,
) -> str:
    return soup_to_markdown(parse_storage(storage_xhtml), image_processor, page_title=page_title)
