"""Smoke tests against fixture XHTML — no network, no OCR, no real render_image."""
from __future__ import annotations

from bs4 import BeautifulSoup

from confluence_md.macros import extract_macro_source
from confluence_md.parser import _normalize_tag_names, storage_to_markdown


def _stub_image_processor(el) -> str:
    return "[IMAGE_PLACEHOLDER]"


def test_basic_html_round_trip():
    storage = "<h1>Title</h1><p>Hello <strong>world</strong>.</p><ul><li>one</li><li>two</li></ul>"
    md = storage_to_markdown(storage, _stub_image_processor, page_title="Demo")
    assert md.startswith("# Demo")
    assert "Hello **world**." in md
    assert "- one" in md
    assert "- two" in md


def test_image_handler_is_invoked():
    storage = '<p>before</p><ac:image ac:alt="x"><ri:attachment ri:filename="diagram.png"/></ac:image><p>after</p>'
    md = storage_to_markdown(storage, _stub_image_processor, page_title="P")
    assert "[IMAGE_PLACEHOLDER]" in md
    assert "before" in md
    assert "after" in md


def test_mermaid_macro_extracted_inline():
    storage = (
        '<ac:structured-macro ac:name="mermaid-cloud">'
        '<ac:plain-text-body><![CDATA[graph TD\nA-->B]]></ac:plain-text-body>'
        '</ac:structured-macro>'
    )
    md = storage_to_markdown(storage, _stub_image_processor, page_title="P")
    assert "```mermaid" in md
    assert "graph TD" in md
    assert "A-->B" in md


def test_plantuml_macro_extracted_inline():
    storage = (
        '<ac:structured-macro ac:name="plantuml">'
        '<ac:plain-text-body><![CDATA[@startuml\nAlice -> Bob\n@enduml]]></ac:plain-text-body>'
        '</ac:structured-macro>'
    )
    md = storage_to_markdown(storage, _stub_image_processor, page_title="P")
    assert "```plantuml" in md
    assert "Alice -> Bob" in md


def test_code_macro_with_language():
    storage = (
        '<ac:structured-macro ac:name="code">'
        '<ac:parameter ac:name="language">java</ac:parameter>'
        '<ac:plain-text-body><![CDATA[int x = 1;]]></ac:plain-text-body>'
        '</ac:structured-macro>'
    )
    md = storage_to_markdown(storage, _stub_image_processor, page_title="P")
    assert "```java" in md
    assert "int x = 1;" in md


def test_info_panel_becomes_blockquote():
    storage = (
        '<ac:structured-macro ac:name="info">'
        '<ac:rich-text-body><p>be careful</p></ac:rich-text-body>'
        '</ac:structured-macro>'
    )
    md = storage_to_markdown(storage, _stub_image_processor, page_title="P")
    assert "> **Info:**" in md
    assert "be careful" in md


def test_drawio_macro_detected_but_source_not_inline():
    storage = (
        '<ac:structured-macro ac:name="drawio">'
        '<ac:parameter ac:name="diagramName">Flow</ac:parameter>'
        '</ac:structured-macro>'
    )
    soup = BeautifulSoup(storage, "html.parser")
    _normalize_tag_names(soup)
    macro_el = soup.find("ac_structured-macro")
    info = extract_macro_source(macro_el)
    assert info is not None
    assert info.type == "drawio"
    assert info.inline is False


def test_unknown_macro_passes_text_through():
    storage = (
        '<ac:structured-macro ac:name="randomthing">'
        '<ac:rich-text-body><p>kept</p></ac:rich-text-body>'
        '</ac:structured-macro>'
    )
    md = storage_to_markdown(storage, _stub_image_processor, page_title="P")
    assert "kept" in md
