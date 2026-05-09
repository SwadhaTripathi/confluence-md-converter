"""Image handling: gather every signal we can extract about a Confluence image
(macro source, alt text, caption, OCR), then hand off to render_image() — the
single place where Decisions A and B (OCR strictness + TODO marker style) become code.

YOU implement render_image(). Everything else is plumbing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from bs4 import Tag

from . import ocr
from .macros import find_wrapping_macro


# Characters that Windows refuses in filenames. Linux is more permissive but '?'
# also breaks markdown image refs (renderers parse it as a query-string start),
# so sanitizing for the strictest target gives consistent behavior everywhere.
_FORBIDDEN_NAME_CHARS = re.compile(r'[<>:"/\\|?*\s]+')


def _safe_local_name(name: str, max_len: int = 100) -> str:
    """Make `name` safe to use as both an on-disk filename and a markdown image ref.

    Confluence allows attachments named like `GetClipboardImage.ashx?Id=...&pkey=...`
    (when images are pasted from Outlook clipboard). Those names contain characters
    Windows rejects in `open()`, so we collapse them while keeping enough of the
    original to remain recognizable.
    """
    safe = _FORBIDDEN_NAME_CHARS.sub("_", name or "").strip("._")
    if not safe:
        return "unnamed"
    return safe[:max_len]

if TYPE_CHECKING:
    from .fetcher import Attachment, ConfluenceClient


@dataclass
class ImageContext:
    """Everything the renderer knows about one image on the page."""
    image_filename: str
    local_path: str               # path of the downloaded image, relative to the .md file
    alt_text: str                 # from ac:image's ac:alt attribute (may be empty)
    caption: str                  # from <ac:caption> or nothing (may be empty)
    macro_type: Optional[str]     # "mermaid" | "plantuml" | "drawio" | "gliffy" | None
    macro_source: Optional[str]   # diagram source as text, or None if not extractable
    ocr_text: str                 # tesseract output ("" if OCR off / unavailable / failed)
    ocr_confidence: float         # 0.0–1.0; 0.0 means "no useful OCR signal"
    todo_id: str                  # sequential id like "img-001"; referenced by sidecar TODO file


@dataclass
class TodoSidecar:
    """Collects images that have no extractable description, for human follow-up."""
    entries: list[dict] = field(default_factory=list)
    _counter: int = 0

    def next_id(self) -> str:
        self._counter += 1
        return f"img-{self._counter:03d}"

    def add(self, todo_id: str, filename: str, ocr_hint: str) -> None:
        self.entries.append({"id": todo_id, "filename": filename, "ocr_hint": ocr_hint})

    def render(self, page_title: str) -> str:
        if not self.entries:
            return f"# TODO — diagrams needing description\n\nPage: {page_title}\n\n_All diagrams had extractable descriptions. Nothing to do._\n"
        lines = [f"# TODO — diagrams needing description", f"", f"Page: {page_title}", ""]
        for e in self.entries:
            lines.append(f"## {e['id']} — {e['filename']}")
            if e["ocr_hint"]:
                lines.append(f"")
                lines.append(f"OCR hint: {e['ocr_hint']!r}")
            lines.append(f"")
            lines.append(f"_Describe this diagram in 1-3 sentences and replace the corresponding HTML comment in the main .md file._")
            lines.append(f"")
        return "\n".join(lines)


def _attr(tag: Tag, *names: str) -> str:
    for n in names:
        v = tag.get(n)
        if v:
            return v
    return ""


def _extract_caption(image_el: Tag) -> str:
    """Confluence caption lives in <ac:caption> as a child of the <ac:image> element."""
    for child in image_el.children:
        if isinstance(child, Tag) and child.name in {"ac:caption", "ac_caption"}:
            return child.get_text(" ", strip=True)
    return ""


def _resolve_filename(image_el: Tag) -> Optional[str]:
    """Find the attachment filename or external URL that the <ac:image> points at."""
    att = image_el.find(["ri:attachment", "ri_attachment"])
    if att is not None:
        return _attr(att, "ri:filename", "ri_filename") or None
    url = image_el.find(["ri:url", "ri_url"])
    if url is not None:
        return _attr(url, "ri:value", "ri_value") or None
    return None


def process_image(
    image_el: Tag,
    *,
    attachments_by_name: dict[str, "Attachment"],
    output_dir: Path,
    client: Optional["ConfluenceClient"],
    todo: TodoSidecar,
    ocr_enabled: bool,
) -> str:
    """Build the ImageContext for a single <ac:image> element and call render_image().

    Returns the markdown block to substitute in place of the <ac:image>.
    """
    filename = _resolve_filename(image_el)
    if not filename:
        return ""

    local_filename = _safe_local_name(filename)
    images_dir = output_dir / "images"
    local_path = images_dir / local_filename
    if client is not None and filename in attachments_by_name and not local_path.exists():
        try:
            client.download_attachment(attachments_by_name[filename], local_path)
        except Exception as e:
            import sys
            print(f"  warn: skipping image '{filename}' — {e}", file=sys.stderr)

    macro = find_wrapping_macro(image_el)
    macro_type = macro.type if macro else None
    macro_source = macro.source if (macro and macro.inline and macro.source) else None

    ocr_text, ocr_conf = ("", 0.0)
    if ocr_enabled and local_path.exists() and ocr.is_available():
        ocr_text, ocr_conf = ocr.extract_text(local_path)

    todo_id = todo.next_id()
    has_description = bool(macro_source) or bool(_attr(image_el, "ac:alt", "ac_alt")) or bool(_extract_caption(image_el))
    if not has_description:
        todo.add(todo_id, filename, ocr_text)

    ctx = ImageContext(
        image_filename=filename,
        local_path=str(Path("images") / local_filename).replace("\\", "/"),
        alt_text=_attr(image_el, "ac:alt", "ac_alt"),
        caption=_extract_caption(image_el),
        macro_type=macro_type,
        macro_source=macro_source,
        ocr_text=ocr_text,
        ocr_confidence=ocr_conf,
        todo_id=todo_id,
    )
    return render_image(ctx)


# ──────────────────────────────────────────────────────────────────────────────
# YOUR CONTRIBUTION — write the body of this function.
# ──────────────────────────────────────────────────────────────────────────────
def render_image(ctx: ImageContext) -> str:
    """Produce the markdown block for ONE image, combining every signal we have.

    This function embodies the design decisions from the planning conversation:

      Decision A → INCLUDE OCR text with a confidence tag (lossless capture).
                   Even low-confidence OCR has value; we tag it so a future filter
                   or smarter LLM in the loop can decide what to trust.

      Decision B → MAIN .md uses HTML comments (invisible in rendered preview but
                   indexed by embedders). The sidecar TODO file (managed by the
                   caller, not by you) lists images that need human description.

    Inputs available on `ctx`:
      ctx.image_filename, ctx.local_path        → for the markdown image reference
      ctx.alt_text, ctx.caption                 → author's intent (may be empty)
      ctx.macro_type, ctx.macro_source          → strongest signal when present
                                                  (mermaid/plantuml source as text)
      ctx.ocr_text, ctx.ocr_confidence          → noisy but lossless extra signal
      ctx.todo_id                               → reference key into sidecar TODO file

    Goals:
      • A reader of the rendered markdown sees a sensible image + caption.
      • A RAG embedder ingests every textual signal we have so semantic search
        works *without* a vision model.
      • Empty / missing fields don't produce ugly placeholders like "alt: None".

    Suggested output anatomy (you decide ordering, formatting, and what to skip):

        ![<alt or filename>](<local_path> "<caption if any>")

        <!-- todo: <id>; ocr-confidence: <0.00> -->

        **Caption:** <caption>
        **Diagram source (<macro_type>):**
        ```<macro_type>
        <macro_source>
        ```
        **OCR text:** <ocr_text>

    Return the markdown string (with leading/trailing blank lines so it sits cleanly
    in surrounding prose). Return "" to skip the image entirely.
    """
    alt = (ctx.alt_text or ctx.image_filename).strip()
    safe_caption = ctx.caption.replace('"', "")
    title_attr = f' "{safe_caption}"' if ctx.caption else ""
    parts = [f"![{alt}]({ctx.local_path}{title_attr})", ""]

    meta = [f"todo: {ctx.todo_id}"]
    if ctx.ocr_text:
        meta.append(f"ocr-confidence: {ctx.ocr_confidence:.2f}")
    parts.append(f"<!-- {'; '.join(meta)} -->")

    if ctx.caption:
        parts.append(f"\n**Caption:** {ctx.caption}")

    if ctx.macro_source and ctx.macro_type:
        parts.append(f"\n**Diagram source ({ctx.macro_type}):**")
        parts.append(f"```{ctx.macro_type}\n{ctx.macro_source}\n```")

    if ctx.ocr_text:
        ocr_clean = " ".join(ctx.ocr_text.split())
        parts.append(f"\n**OCR text:** {ocr_clean}")

    return "\n\n" + "\n".join(parts) + "\n\n"
