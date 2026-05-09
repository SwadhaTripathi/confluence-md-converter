"""Tests for expand_drawio_macros — soup mutation, attachment lookup."""
from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup

from confluence_md.parser import parse_storage
from confluence_md.preprocess import expand_drawio_macros


SAMPLE_DRAWIO = """<mxfile>
  <diagram name="Recovery">
    <mxGraphModel>
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>
        <mxCell id="a" value="Start" vertex="1" parent="1"/>
        <mxCell id="b" value="End" vertex="1" parent="1"/>
        <mxCell id="e1" source="a" target="b" edge="1" parent="1"/>
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
"""


def test_drawio_macro_gets_summary_injected(tmp_path: Path):
    drawio_file = tmp_path / "recovery.drawio"
    drawio_file.write_text(SAMPLE_DRAWIO, encoding="utf-8")

    storage = (
        '<ac:structured-macro ac:name="drawio">'
        '<ac:parameter ac:name="diagramName">recovery</ac:parameter>'
        '</ac:structured-macro>'
    )
    soup = parse_storage(storage)

    def loader(name: str):
        return drawio_file if name == "recovery" else None

    expanded = expand_drawio_macros(soup, drawio_loader=loader)
    assert expanded == 1

    # The macro should now contain a synthetic plain-text-body with the summary
    macro = soup.find("ac_structured-macro")
    body = macro.find("ac_plain-text-body")
    assert body is not None
    text = body.get_text()
    assert "Diagram: Recovery" in text
    assert "- Start" in text
    assert "- End" in text


def test_drawio_loader_returning_none_skips_quietly():
    storage = (
        '<ac:structured-macro ac:name="drawio">'
        '<ac:parameter ac:name="diagramName">missing</ac:parameter>'
        '</ac:structured-macro>'
    )
    soup = parse_storage(storage)
    expanded = expand_drawio_macros(soup, drawio_loader=lambda _: None)
    assert expanded == 0
    macro = soup.find("ac_structured-macro")
    assert macro.find("ac_plain-text-body") is None


def test_non_drawio_macros_untouched(tmp_path: Path):
    storage = (
        '<ac:structured-macro ac:name="mermaid-cloud">'
        '<ac:plain-text-body>graph TD\nA-->B</ac:plain-text-body>'
        '</ac:structured-macro>'
    )
    soup = parse_storage(storage)
    expanded = expand_drawio_macros(soup, drawio_loader=lambda _: tmp_path / "anything.drawio")
    assert expanded == 0


def test_resolve_internal_links_tags_resolvable_pages():
    from confluence_md.preprocess import resolve_internal_links

    storage = (
        '<p>See '
        '<ac:link><ri:page ri:content-title="Other Page" ri:space-key="FG"/>'
        '<ac:link-body>that page</ac:link-body></ac:link>'
        ' for context.</p>'
    )
    soup = parse_storage(storage)
    calls = []

    def resolver(title, space_key):
        calls.append((title, space_key))
        return "https://example.atlassian.net/wiki/spaces/FG/pages/999/Other-Page"

    n = resolve_internal_links(soup, link_resolver=resolver)
    assert n == 1
    assert calls == [("Other Page", "FG")]
    link = soup.find("ac_link")
    assert link.get("data-resolved-url") == "https://example.atlassian.net/wiki/spaces/FG/pages/999/Other-Page"


def test_resolve_internal_links_skips_unresolvable_quietly():
    from confluence_md.preprocess import resolve_internal_links

    storage = (
        '<ac:link><ri:page ri:content-title="Missing"/>'
        '<ac:link-body>broken link</ac:link-body></ac:link>'
    )
    soup = parse_storage(storage)
    n = resolve_internal_links(soup, link_resolver=lambda t, s: None)
    assert n == 0
    link = soup.find("ac_link")
    assert link.get("data-resolved-url") is None


def test_resolve_internal_links_caches_repeated_titles():
    from confluence_md.preprocess import resolve_internal_links

    storage = "".join(
        f'<ac:link><ri:page ri:content-title="Same Page"/>'
        f'<ac:link-body>ref {i}</ac:link-body></ac:link>'
        for i in range(3)
    )
    soup = parse_storage(storage)
    call_count = {"n": 0}

    def resolver(title, space_key):
        call_count["n"] += 1
        return "https://x/p"

    n = resolve_internal_links(soup, link_resolver=resolver)
    assert n == 3
    assert call_count["n"] == 1


def test_full_pipeline_drawio_emits_fenced_code_block(tmp_path: Path):
    """End-to-end: drawio macro → preprocess → soup_to_markdown produces a ```drawio block."""
    from confluence_md.parser import soup_to_markdown

    drawio_file = tmp_path / "recovery.drawio"
    drawio_file.write_text(SAMPLE_DRAWIO, encoding="utf-8")
    storage = (
        '<p>before</p>'
        '<ac:structured-macro ac:name="drawio">'
        '<ac:parameter ac:name="diagramName">recovery</ac:parameter>'
        '</ac:structured-macro>'
        '<p>after</p>'
    )
    soup = parse_storage(storage)
    expand_drawio_macros(soup, drawio_loader=lambda n: drawio_file if n == "recovery" else None)

    md = soup_to_markdown(soup, lambda el: "[IMG]", page_title="Test")
    assert "```drawio" in md
    assert "Diagram: Recovery" in md
    assert "- Start" in md
    assert "before" in md
    assert "after" in md
