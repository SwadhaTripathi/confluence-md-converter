"""Tests for the drawio decoder/summarizer — round-trip compress/decompress, multi-diagram, HTML labels."""
from __future__ import annotations

import base64
import zlib
from urllib.parse import quote

from confluence_md import drawio


SIMPLE_UNCOMPRESSED = """<mxfile>
  <diagram name="Page-1">
    <mxGraphModel>
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>
        <mxCell id="a" value="Start" vertex="1" parent="1"/>
        <mxCell id="b" value="End" vertex="1" parent="1"/>
        <mxCell id="e1" source="a" target="b" edge="1" parent="1" value="go"/>
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
"""


def _drawio_compress(xml: str) -> str:
    """Reproduce drawio's compression algorithm so we can build a fixture."""
    encoded = quote(xml).encode("utf-8")
    compressor = zlib.compressobj(level=9, method=zlib.DEFLATED, wbits=-zlib.MAX_WBITS)
    deflated = compressor.compress(encoded) + compressor.flush()
    return base64.b64encode(deflated).decode("ascii")


def test_summarize_uncompressed():
    out = drawio.summarize(SIMPLE_UNCOMPRESSED)
    assert "Diagram: Page-1" in out
    assert "- Start" in out
    assert "- End" in out
    assert "- Start -> End (go)" in out


def test_summarize_compressed():
    inner = "<mxGraphModel><root><mxCell id='1'/><mxCell id='a' value='Foo' vertex='1' parent='1'/><mxCell id='b' value='Bar' vertex='1' parent='1'/><mxCell id='e' source='a' target='b' edge='1' parent='1'/></root></mxGraphModel>"
    payload = _drawio_compress(inner)
    xml = f"<mxfile><diagram name='Compressed'>{payload}</diagram></mxfile>"
    out = drawio.summarize(xml)
    assert "Diagram: Compressed" in out
    assert "- Foo" in out
    assert "- Bar" in out
    assert "- Foo -> Bar" in out


def test_summarize_multi_diagram():
    xml = (
        "<mxfile>"
        "<diagram name='A'><mxGraphModel><root><mxCell id='1'/><mxCell id='x' value='X1' vertex='1' parent='1'/></root></mxGraphModel></diagram>"
        "<diagram name='B'><mxGraphModel><root><mxCell id='1'/><mxCell id='y' value='Y1' vertex='1' parent='1'/></root></mxGraphModel></diagram>"
        "</mxfile>"
    )
    out = drawio.summarize(xml)
    assert "Diagram: A" in out
    assert "Diagram: B" in out
    assert "- X1" in out
    assert "- Y1" in out


def test_summarize_strips_html_in_labels():
    xml = "<mxfile><diagram name='HTML'><mxGraphModel><root><mxCell id='1'/><mxCell id='n' value='&lt;b&gt;Bold&lt;/b&gt;&lt;br&gt;line2' vertex='1' parent='1'/></root></mxGraphModel></diagram></mxfile>"
    out = drawio.summarize(xml)
    assert "- Bold line2" in out
    assert "<b>" not in out


def test_summarize_empty_input_returns_empty():
    assert drawio.summarize("") == ""
    assert drawio.summarize("   ") == ""


def test_summarize_invalid_xml_returns_empty():
    assert drawio.summarize("<not valid xml") == ""


def test_summarize_unlabelled_vertices_skipped_from_node_list():
    xml = "<mxfile><diagram name='Q'><mxGraphModel><root><mxCell id='1'/><mxCell id='a' vertex='1' parent='1'/><mxCell id='b' value='Real' vertex='1' parent='1'/></root></mxGraphModel></diagram></mxfile>"
    out = drawio.summarize(xml)
    assert "- Real" in out
    # Empty-label vertex should not appear as "- "
    lines = out.splitlines()
    bullet_lines = [ln for ln in lines if ln.strip().startswith("-")]
    assert all("Real" in ln or "->" in ln for ln in bullet_lines)
