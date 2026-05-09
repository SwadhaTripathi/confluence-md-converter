"""Unit tests for render_image() — pure function, no I/O."""
from __future__ import annotations

from confluence_md.image_handler import ImageContext, render_image


def _ctx(**overrides) -> ImageContext:
    defaults = dict(
        image_filename="diagram.png",
        local_path="images/diagram.png",
        alt_text="",
        caption="",
        macro_type=None,
        macro_source=None,
        ocr_text="",
        ocr_confidence=0.0,
        todo_id="img-001",
    )
    defaults.update(overrides)
    return ImageContext(**defaults)


def test_macro_source_with_caption_and_ocr():
    md = render_image(_ctx(
        alt_text="recovery handshake",
        caption="Sequence: controller → arm → sensor",
        macro_type="mermaid",
        macro_source="sequenceDiagram\nA->>B: hi",
        ocr_text="A B hi",
        ocr_confidence=0.78,
        todo_id="img-002",
    ))
    assert "![recovery handshake](images/diagram.png" in md
    assert '"Sequence: controller → arm → sensor"' in md
    assert "<!-- todo: img-002; ocr-confidence: 0.78 -->" in md
    assert "**Caption:** Sequence: controller → arm → sensor" in md
    assert "```mermaid" in md
    assert "sequenceDiagram" in md
    assert "**OCR text:** A B hi" in md


def test_alt_only_no_macro_no_ocr():
    md = render_image(_ctx(alt_text="login screen"))
    assert "![login screen](images/diagram.png)" in md
    assert "<!-- todo: img-001 -->" in md  # no ocr-confidence when ocr_text is empty
    assert "Caption" not in md
    assert "Diagram source" not in md
    assert "OCR text" not in md


def test_ocr_only_falls_back_to_filename_for_alt():
    md = render_image(_ctx(
        ocr_text="Username  Password\nLogin",
        ocr_confidence=0.92,
    ))
    assert "![diagram.png](images/diagram.png)" in md  # alt falls back to filename
    assert "ocr-confidence: 0.92" in md
    # Multi-line OCR collapsed to single line
    assert "**OCR text:** Username Password Login" in md


def test_nothing_extractable_still_emits_image_and_todo():
    md = render_image(_ctx(image_filename="hand_sketch.jpg", local_path="images/hand_sketch.jpg"))
    assert "![hand_sketch.jpg](images/hand_sketch.jpg)" in md
    assert "<!-- todo: img-001 -->" in md
    # Confirm the only sections present are image + todo comment
    assert "Caption" not in md
    assert "Diagram source" not in md
    assert "OCR text" not in md


def test_caption_with_double_quote_does_not_break_title_syntax():
    md = render_image(_ctx(caption='He said "hi"'))
    assert '![diagram.png](images/diagram.png "He said hi")' in md
    assert "**Caption:** He said" in md


def test_drawio_detected_no_inline_source_skips_diagram_block():
    md = render_image(_ctx(macro_type="drawio", macro_source=None, ocr_text="A B C", ocr_confidence=0.4))
    assert "Diagram source" not in md
    assert "**OCR text:** A B C" in md


def test_pads_with_blank_lines_for_clean_inline_placement():
    md = render_image(_ctx())
    assert md.startswith("\n\n")
    assert md.endswith("\n\n")


def test_safe_local_name_strips_forbidden_chars():
    from confluence_md.image_handler import _safe_local_name

    name = "GetClipboardImage.ashx?Id=bd14c311&DC=GEU4&pkey=abc"
    safe = _safe_local_name(name)
    assert "?" not in safe        # would crash open() on Windows
    assert "/" not in safe
    assert "\\" not in safe
    assert "GetClipboardImage" in safe
    # & is allowed on Windows, so it stays — only the path-illegal chars get replaced
    assert safe == "GetClipboardImage.ashx_Id=bd14c311&DC=GEU4&pkey=abc"


def test_safe_local_name_truncates_long_names():
    from confluence_md.image_handler import _safe_local_name
    assert len(_safe_local_name("a" * 250)) == 100


def test_safe_local_name_handles_empty():
    from confluence_md.image_handler import _safe_local_name
    assert _safe_local_name("") == "unnamed"
    assert _safe_local_name("   ") == "unnamed"


def test_caption_does_not_leak_between_sibling_images():
    """Regression: an image without its own <ac:caption> must not pick up a sibling's caption."""
    from bs4 import BeautifulSoup

    from confluence_md.image_handler import _extract_caption
    from confluence_md.parser import _normalize_tag_names

    storage = (
        '<p>'
        '<ac:image><ri:attachment ri:filename="a.png"/><ac:caption>caption A</ac:caption></ac:image>'
        '<ac:image><ri:attachment ri:filename="b.png"/></ac:image>'
        '</p>'
    )
    soup = BeautifulSoup(storage, "html.parser")
    _normalize_tag_names(soup)
    images = soup.find_all("ac_image")
    assert _extract_caption(images[0]) == "caption A"
    assert _extract_caption(images[1]) == ""
