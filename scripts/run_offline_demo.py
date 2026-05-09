"""Offline demo: run the full converter pipeline against a fixture XHTML file
without network or auth. Mirrors what the live CLI does, including drawio macro
expansion (the loader reads the .drawio file from the local fixtures folder
instead of downloading it from Confluence).

Usage:
    python scripts/run_offline_demo.py
"""
from __future__ import annotations

from pathlib import Path

from confluence_md.image_handler import TodoSidecar, process_image
from confluence_md.parser import parse_storage, soup_to_markdown
from confluence_md.preprocess import expand_drawio_macros


PAGE_TITLE = "Revive all wafer handling devices rev 4"
FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
FIXTURE_PAGE = FIXTURES / "wafer_handling_page.xhtml"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "examples"


def fixture_drawio_loader(diagram_name: str) -> Path | None:
    p = FIXTURES / f"{diagram_name}.drawio"
    return p if p.exists() else None


def main() -> None:
    storage_xhtml = FIXTURE_PAGE.read_text(encoding="utf-8")

    page_dir = OUTPUT_DIR / "demo_output"
    page_dir.mkdir(parents=True, exist_ok=True)
    todo = TodoSidecar()

    soup = parse_storage(storage_xhtml)
    expanded = expand_drawio_macros(soup, drawio_loader=fixture_drawio_loader)

    def img_proc(el):
        return process_image(
            el,
            attachments_by_name={},
            output_dir=page_dir,
            client=None,
            todo=todo,
            ocr_enabled=False,
        )

    md = soup_to_markdown(soup, img_proc, page_title=PAGE_TITLE)

    md_path = OUTPUT_DIR / "converter_output_demo.md"
    md_path.write_text(md, encoding="utf-8")
    todo_path = OUTPUT_DIR / "converter_output_demo.todo.md"
    todo_path.write_text(todo.render(PAGE_TITLE), encoding="utf-8")

    print(f"expanded {expanded} drawio macro(s)")
    print(f"wrote {md_path}")
    print(f"wrote {todo_path}")


if __name__ == "__main__":
    main()
