"""CLI entry point: converts a Confluence page (or a tree) to markdown for RAG ingestion."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import truststore
from dotenv import load_dotenv

# Use the OS trust store (Windows Certificate Store / macOS keychain / Linux ca-certs)
# instead of the bundled certifi PEM. This makes corporate HTTPS-inspecting proxies
# work transparently because IT already installs the corporate CA in the OS store.
# Must run before any HTTPS request — keep at module import time.
truststore.inject_into_ssl()

from .fetcher import Attachment, ConfluenceClient
from .image_handler import TodoSidecar, process_image
from .parser import parse_storage, soup_to_markdown
from .preprocess import expand_drawio_macros, resolve_internal_links


def _slugify(title: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", title).strip().lower()
    slug = re.sub(r"[\s_-]+", "-", slug)
    return slug or "page"


def _make_drawio_loader(
    client: ConfluenceClient,
    attachments_by_name: dict[str, Attachment],
    download_dir: Path,
):
    download_dir.mkdir(parents=True, exist_ok=True)

    def loader(diagram_name: str) -> Path | None:
        for cand in (f"{diagram_name}.drawio", f"{diagram_name}.tmp", diagram_name):
            att = attachments_by_name.get(cand)
            if att is None:
                continue
            local = download_dir / cand
            if local.exists():
                return local
            try:
                client.download_attachment(att, local)
            except Exception as e:
                print(f"  warn: skipping drawio '{cand}' — {e}", file=sys.stderr)
                return None
            return local
        return None

    return loader


def _convert_one(client: ConfluenceClient, page_id: str, out_dir: Path, ocr_enabled: bool) -> Path:
    page = client.fetch_page(page_id)
    attachments = client.list_attachments(page_id)
    attachments_by_name = {a.filename: a for a in attachments}

    page_dir = out_dir / _slugify(page.title)
    page_dir.mkdir(parents=True, exist_ok=True)
    todo = TodoSidecar()

    soup = parse_storage(page.storage_xhtml)
    drawio_loader = _make_drawio_loader(client, attachments_by_name, page_dir / "diagrams")
    expanded = expand_drawio_macros(soup, drawio_loader=drawio_loader)
    if expanded:
        print(f"  expanded {expanded} drawio macro(s)", file=sys.stderr)
    linked = resolve_internal_links(soup, link_resolver=client.find_page_url)
    if linked:
        print(f"  resolved {linked} internal link(s)", file=sys.stderr)

    def image_processor(el):
        return process_image(
            el,
            attachments_by_name=attachments_by_name,
            output_dir=page_dir,
            client=client,
            todo=todo,
            ocr_enabled=ocr_enabled,
        )

    md = soup_to_markdown(soup, image_processor, page_title=page.title)

    md_path = page_dir / f"{_slugify(page.title)}.md"
    md_path.write_text(md, encoding="utf-8")

    todo_path = page_dir / f"{_slugify(page.title)}.todo.md"
    todo_path.write_text(todo.render(page.title), encoding="utf-8")

    return md_path


def main(argv: list[str] | None = None) -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(
        prog="confluence-to-md",
        description="Convert a Confluence page to RAG-friendly markdown.",
    )
    parser.add_argument("page", help="Confluence page URL or numeric page ID")
    parser.add_argument("--out", default="./output", help="Output directory (default: ./output)")
    parser.add_argument("--no-ocr", action="store_true", help="Skip OCR even if Tesseract is installed")
    parser.add_argument("--recursive", action="store_true", help="Also export every descendant page")
    args = parser.parse_args(argv)

    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    ocr_enabled = not args.no_ocr

    try:
        client = ConfluenceClient()
    except KeyError as e:
        print(f"error: missing env var {e.args[0]} — copy .env.example to .env and fill it in", file=sys.stderr)
        return 2

    try:
        root_id = client.parse_page_id(args.page)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    page_ids = list(client.iter_pages_under(root_id)) if args.recursive else [root_id]
    for pid in page_ids:
        print(f"converting page {pid}…", file=sys.stderr)
        md_path = _convert_one(client, pid, out_dir, ocr_enabled)
        print(f"  → {md_path}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
