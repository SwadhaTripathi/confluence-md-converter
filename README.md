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
| **Drawio macros** | **`.drawio` attachment downloaded, decompressed, and rendered as a structured node/edge listing** |
| Gliffy macros | macro detected; image rendered + OCR'd (source decoding TBD) |
| Pasted images (clipboard, Outlook, etc.) | downloaded locally with sanitized filenames |
| Internal Confluence page links | resolved to absolute URLs (`[text](https://…)`) |
| Anything still missing | logged in a sidecar `*.todo.md` for human follow-up |

---

## Quickstart — clone to first conversion

Step-by-step from a fresh machine. Tested on Windows 11 + PowerShell; commands work on
macOS/Linux with the obvious tweaks (forward slashes, `source .venv/bin/activate`).

### 1. Clone the repo

```powershell
git clone git@github.com:SwadhaTripathi/confluence-md-converter.git
cd confluence-md-converter
```

If you don't have SSH set up:

```powershell
git clone https://github.com/SwadhaTripathi/confluence-md-converter.git
cd confluence-md-converter
```

### 2. Create and activate a Python virtual environment

Python 3.10 or newer required.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Your prompt should now show `(.venv)` at the start. If activation is blocked by
`ExecutionPolicy`, run this first (process-scoped, no admin needed):

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### 3. Install the package

```powershell
pip install -e ".[ocr]"
```

Drop `[ocr]` if you don't want Tesseract — OCR is optional and the tool degrades cleanly
without it. Verify the install worked:

```powershell
confluence-to-md --help
```

Expected: a help screen showing `page`, `--out`, `--no-ocr`, `--recursive`.

If you instead see `ModuleNotFoundError: No module named 'confluence_md.cli'`, your
editable install is stale — clean it and reinstall:

```powershell
pip uninstall -y confluence-md-converter
pip install -e ".[ocr]"
```

### 4. Get an Atlassian API token

1. Open <https://id.atlassian.com/manage-profile/security/api-tokens>
2. Click **Create API token** (a "scoped" token is fine — give it `read:page:confluence`,
   `read:attachment:confluence`, `read:space:confluence`)
3. Copy the token — you only see it once

### 5. Configure your `.env`

Copy the template and fill in real values:

```powershell
copy .env.example .env
notepad .env
```

```env
CONFLUENCE_BASE_URL=https://your-org.atlassian.net
CONFLUENCE_EMAIL=you@example.com
CONFLUENCE_API_TOKEN=<the token from step 5>
```

> **Do not commit `.env`.** It's already in `.gitignore`. Never put your token in
> `.env.example`.

### 6. Run your first conversion

```powershell
confluence-to-md "https://your-org.atlassian.net/wiki/spaces/X/pages/1234567/Title" --out ./output
```

Expected output:

```
converting page 1234567…
  expanded N drawio macro(s)
  resolved M internal link(s)
  → C:\…\output\<page-slug>\<page-slug>.md
```

You'll find the result at `output/<page-slug>/`:

```
output/<page-slug>/
├── <page-slug>.md            ← primary RAG input — drop this into your pipeline
├── <page-slug>.todo.md       ← optional: 1-line descriptions for diagrams without alt-text
├── images/                   ← every page image, downloaded and locally referenced
└── diagrams/                 ← original .drawio source files (decoded inline into the .md)
```

### 7. Verify it worked

Open `<page-slug>.md` and check that:

- The text content matches the source page
- Tables, lists, and headings are preserved
- Drawio sections show up as fenced ` ```drawio ` code blocks with node/edge listings
- Image references point at files inside `images/` (not `blob:` URLs)

---

---

## Security: what's safe to share

Two pieces of state in this project have very different sensitivity. Treat them
accordingly.

| File / artifact | Contains | Safe to share? | Notes |
|---|---|---|---|
| `.env` | Your Atlassian email + API token | **Never share, never commit** | Read-only token for Confluence; if it leaks, anyone with it can impersonate your read access. Already in `.gitignore` |
| `.env.example` | Placeholder template (no real values) | Yes | Committed, used to bootstrap teammates' setups |
| Converted `.md` files | The page's text + diagram source + image refs — *no auth tokens, no API keys* | As broadly as the source Confluence page allows | Output inherits the sensitivity of its source page |
| Downloaded `images/` and `diagrams/` | The actual page attachments | Same as the source page | These are bytes Confluence served you — share with the same audience |
| `*.todo.md` sidecar | List of images that need 1-line descriptions | Same as the source | No secrets |

**Two checks before publishing converted output:**

1. **`grep -ri "atlassian" output/` shouldn't show your token.** It won't — the converter
   never writes auth values into output — but it's a 3-second sanity check.
2. **Confirm the source page's audience matches the destination.** A page tagged for
   Engineering shouldn't end up in a public RAG index just because the conversion was
   easy. The tool can't enforce this; you can.

The API token *only* exists in `.env` and in HTTP request headers at conversion time.
It is never embedded in the markdown output. You can share the entire `output/<page-slug>/`
folder with anyone authorised to see the original Confluence page.

---

## Useful flags

| Flag | What it does |
|---|---|
| `--recursive` | Convert the page **and every descendant** under the same root |
| `--no-ocr` | Skip OCR even if Tesseract is installed (faster on large pages) |
| `--out PATH` | Output directory (default: `./output`) |

## Tesseract OCR (optional, no admin needed)

If you want OCR on raster screenshots — not strictly required, but adds extra signal to
RAG when an image's text labels matter:

1. Download `tesseract-ocr-w64-setup-…exe` from <https://github.com/UB-Mannheim/tesseract/wiki>
2. Install to a user-writable folder (e.g. `C:\Users\<you>\AppData\Local\Programs\Tesseract-OCR\`)
3. Add that folder to your user `PATH` (no admin)
4. Verify: `tesseract --version`

The tool detects Tesseract automatically; if it's missing, OCR steps are silently skipped
and the rest of the conversion continues.

## Wiring into rag-lab

`rag-lab/src/loaders.py` already handles `.md` files. To index a page:

```powershell
# 1. Convert into rag-lab's docs folder
confluence-to-md <url> --out ../rag-lab/docs/

# 2. Index (from rag-lab/)
python -m src.index ./docs --name confluence_<page-slug>

# 3. Query
python -m src.ask "your question"
```

## Offline demo (no auth needed)

To see the converter end-to-end without setting up `.env`:

```powershell
python scripts/run_offline_demo.py
```

Runs against `tests/fixtures/wafer_handling_page.xhtml` (a representative
engineering-style storage XHTML) and writes:

- `examples/converter_output_demo.md` — what the converter produces
- `examples/converter_output_demo.todo.md` — the sidecar TODO list

Compare to `examples/mcp_markdown_baseline.md` (Atlassian MCP's native markdown of the
same content) to see what extra signals the converter extracts.

## Project structure

```
src/confluence_md/
├── cli.py             # argparse entry point + orchestration
├── fetcher.py         # Confluence REST v2 client (with OS-trust-store SSL)
├── parser.py          # storage XHTML → markdown (markdownify subclass)
├── macros.py          # diagram macro detection + source extraction
├── preprocess.py      # soup-level rewrites (drawio expansion, link resolution)
├── drawio.py          # decompress .drawio files; summarize as nodes + edges text
├── ocr.py             # optional Tesseract wrapper (graceful no-op without it)
└── image_handler.py   # ImageContext + render_image() (design-decision hot spot)
```

## Tests

```powershell
pip install -e ".[dev]"
pytest tests/
```

36 tests, all running against fixture XHTML — no network, no auth.

## Limitations

- **Gliffy macros**: detected but source not yet decoded. The rendered PNG attachment
  is still downloaded; OCR can pick up text labels. Drawio is decoded in full — see
  `src/confluence_md/drawio.py`.
- **Excel / PowerPoint embeds**: image preview only.
- **Pages on Confluence Server / Data Center**: not supported. The fetcher uses Cloud's
  v2 REST API. Server uses different endpoints and different auth (PAT bearer token).

## Sharing with your team

The package is `pip install`-able. Once published to your internal index (or even just
shared as a wheel), teammates run:

```powershell
pip install confluence-md-converter
confluence-to-md <url> --out ./output
```

No copy-pasting scripts.

## Troubleshooting

| Error | Likely cause | Fix |
|---|---|---|
| `confluence-to-md: not recognized` | `.venv` not active | `.\.venv\Scripts\Activate.ps1` |
| `ModuleNotFoundError: No module named 'confluence_md.cli'` | Stale editable install | `pip uninstall -y confluence-md-converter && pip install -e ".[ocr]"` |
| `KeyError: 'CONFLUENCE_BASE_URL'` | `.env` not loaded | Run from project root, confirm `.env` exists (not `.env.txt`) |
| `SSLCertVerificationError` | Corporate proxy not in cert bundle | Already handled — the tool injects the OS trust store at startup. If you still see this, your IT hasn't installed the corporate CA in your user trust store |
| `404` on attachment download | URL prefix bug (legacy) | Already fixed in current version. If reproducing on a fork, ensure `fetcher._absolute_url` adds `/wiki` |
| All images missing on Windows | Filesystem-illegal chars in attachment names | Already fixed — names are sanitized before write |
