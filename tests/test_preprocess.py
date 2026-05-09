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
