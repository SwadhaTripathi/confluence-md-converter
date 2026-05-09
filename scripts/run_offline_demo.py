"""Offline demo: run the full converter pipeline against a fixture XHTML file
without network or auth. Produces the same output shape as the real CLI would
produce against a live Confluence page (minus the actual image downloads).

Usage:
    python scripts/run_offline_demo.py
"""
from __future__ import annotations

from pathlib import Path

from confluence_md.image_handler import TodoSidecar, process_image
from confluence_md.parser import storage_to_markdown


PAGE_TITLE = "Revive all wafer handling devices rev 4"
FIXTURE = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "wafer_handling_page.xhtml"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "examples"


def main() -> None:
    storage_xhtml = FIXTURE.read_text(encoding="utf-8")

    page_dir = OUTPUT_DIR / "demo_output"
    page_dir.mkdir(parents=True, exist_ok=True)
    todo = TodoSidecar()

    def img_proc(el):
        return process_image(
            el,
            attachments_by_name={},
            output_dir=page_dir,
            client=None,
            todo=todo,
            ocr_enabled=False,
        )

    md = storage_to_markdown(storage_xhtml, img_proc, page_title=PAGE_TITLE)

    md_path = OUTPUT_DIR / "converter_output_demo.md"
    md_path.write_text(md, encoding="utf-8")
    todo_path = OUTPUT_DIR / "converter_output_demo.todo.md"
    todo_path.write_text(todo.render(PAGE_TITLE), encoding="utf-8")

    print(f"wrote {md_path}")
    print(f"wrote {todo_path}")
    print(f"\n--- preview ({md_path.name}) ---\n")
    print(md)


if __name__ == "__main__":
    main()
