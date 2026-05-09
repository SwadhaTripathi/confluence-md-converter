# confluence-md-converter

Convert Confluence Cloud pages — including their diagrams — into RAG-friendly markdown,
**without needing a vision model**. Output drops directly into a RAG pipeline like
[`rag-lab`](../rag-lab) (or any other markdown-aware ingester).

## Why this exists

Most RAG pipelines only index text. Confluence pages full of sequence diagrams, flow
charts, and screenshots lose all that meaning at ingestion time. This tool extracts every
*textual* signal it can find about each diagram and weaves it into the markdown so a
text-only embedder still has something to index:

| Source | What we extract |
|---|---|
| Mermaid / PlantUML macros | full diagram source as a fenced code block |
| Drawio / Gliffy macros | macro detected; image rendered + OCR’d |
| Pasted images | alt text, caption, OCR text (Tesseract) |
| Anything still missing | logged in a sidecar `*.todo.md` for human follow-up |

## Install

```powershell
git clone <repo-url> confluence-md-converter
cd confluence-md-converter
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[ocr]"     # drop "[ocr]" if you don't have Tesseract
```

OCR is optional. If `pytesseract` or the Tesseract binary isn't installed, the tool
silently skips OCR and continues — you'll just get fewer signals per image.

### Tesseract on Windows (no admin)

Download the `tesseract-ocr-w64-setup-...exe` from
<https://github.com/UB-Mannheim/tesseract/wiki>, install to a user-writable folder, and
add that folder to your `PATH`. No admin needed.

## Configure auth

Copy `.env.example` to `.env` and fill in:

```
CONFLUENCE_BASE_URL=https://your-org.atlassian.net
CONFLUENCE_EMAIL=you@example.com
CONFLUENCE_API_TOKEN=...
```

Generate the API token at <https://id.atlassian.com/manage-profile/security/api-tokens>.

## Usage

```powershell
# Single page (URL or numeric ID)
confluence-to-md "https://your-org.atlassian.net/wiki/spaces/X/pages/1234567/Title" --out ./output

# Whole subtree (page + descendants)
confluence-to-md 1234567 --recursive --out ./output

# Skip OCR
confluence-to-md 1234567 --no-ocr --out ./output
```

For each page you get a folder:

```
output/<page-slug>/
├── <page-slug>.md            ← drop this into your RAG pipeline
├── <page-slug>.todo.md       ← list of diagrams that need human description
└── images/                   ← downloaded attachments
```

## Wiring into rag-lab

`rag-lab/src/loaders.py` already handles `.md` files. To index a page:

```powershell
# 1. Convert
confluence-to-md <url> --out ../rag-lab/docs/

# 2. Index (from rag-lab/)
python -m src.index ./docs --name confluence_<page-slug>

# 3. Query
python -m src.ask "your question"
```

## Limitations (be honest about what doesn't work yet)

- **Drawio / Gliffy macros**: macro is detected but the source XML (stored as a separate
  attachment) isn't decoded. The rendered PNG + OCR are used as fallback. Future work.
- **Internal Confluence links**: rendered as plain text — not resolved to the linked page.
- **Excel / PowerPoint embeds**: image preview only.
- **No vision model**: hand-drawn flowcharts with no embedded text labels can't be
  meaningfully described. Use the `*.todo.md` sidecar to track these for manual
  annotation.

## Project structure

```
src/confluence_md/
├── cli.py             # argparse entry point + orchestration
├── fetcher.py         # Confluence REST v2 client
├── parser.py          # storage XHTML → markdown (markdownify subclass)
├── macros.py          # diagram macro detection + source extraction
├── ocr.py             # optional Tesseract wrapper (graceful no-op without it)
└── image_handler.py   # ImageContext + render_image() (the design-decision hot spot)
```

## Tests

```powershell
pip install -e ".[dev]"
pytest tests/
```

Tests don't hit the network; they run against fixture XHTML.

## Offline demo (no auth needed)

To see the converter end-to-end without setting up `.env`:

```powershell
python scripts/run_offline_demo.py
```

This runs against `tests/fixtures/wafer_handling_page.xhtml` (a representative
engineering-style storage XHTML) and writes:

- `examples/converter_output_demo.md` — what the converter produces
- `examples/converter_output_demo.todo.md` — the sidecar TODO list

Compare to `examples/mcp_markdown_baseline.md` (Atlassian MCP's native markdown
of the same content) to see what extra signals the converter extracts.

## Sharing with your team

This package is `pip install`-able. Once published to your internal index (or even just
shared as a wheel), teammates run:

```powershell
pip install confluence-md-converter
confluence-to-md <url> --out ./output
```

No copy-pasting scripts.
