# Confluence-to-Markdown Conversion Report

| Field | Value |
|---|---|
| **Source page** | [Revive all wafer handling devices rev 4](https://pdc-amat-prod.atlassian.net/wiki/spaces/FG/pages/1260159018/Revive+all+wafer+handling+devices+rev+4) |
| **Page version** | 15 (last edited 2026-05-03) |
| **Initial conversion** | 2026-05-09 |
| **Re-converted after gap fixes** | 2026-05-09 (later same day) |
| **Output bundle** | `output/revive-all-wafer-handling-devices-rev-4/` |
| **Utility** | `confluence-md-converter` v0.1.0 |
| **Purpose** | Make image-and-diagram-heavy specifications ingestible by RAG |

---

## Executive summary

The utility converted the source Confluence page — a 35 KB engineering specification containing 9 tables, 3 embedded images, and 2 draw.io flow diagrams — into a single RAG-ready Markdown bundle with **zero loss of textual content**, **all 3 page images downloaded**, and **complete extraction of diagram logic** that the source itself does not expose as text. An initial run of the verification surfaced a Windows filename-handling defect that prevented two of the images from saving; the defect was identified during this verification and fixed, after which a re-run produced a fully complete output bundle. The output is approved for ingestion into the RAG pipeline.

---

## Why this matters

Every RAG implementation indexes text. Confluence pages full of sequence diagrams, flow charts, and screenshots normally lose 30–60% of their meaning at ingestion time because that meaning lives inside images. This utility extracts the *textual* signal embedded in each diagram — node labels, transitions, edge captions — so that a text-only embedding model can answer questions like *"what triggers the Manual Recovery Flow?"* against content that previously existed only as pixels.

---

## Verification method

The output Markdown file was compared element-by-element against the live Confluence source, retrieved through Atlassian's official API at the same point in time. Headings, paragraphs, lists, tables, images, and diagrams were checked individually. Diagram contents were validated by counting and naming the nodes and edges captured in the output versus the visual diagram in Confluence.

---

## Coverage results

| Element | In source | In output | Status |
|---|---|---|---|
| Page title | ✓ | ✓ | Captured |
| Intro section + 3 inline review comments | ✓ | ✓ | Captured verbatim |
| 5 numbered requirement sections (REQ 001 – REQ 005) | ✓ | ✓ | Captured |
| 9 data tables (state machine, error matrices, full loading sequence, domains affected, etc.) | ✓ | ✓ | All rows + columns intact |
| Bold / strikethrough emphasis | ✓ | ✓ | Preserved |
| Native PNG attachment (REQ 001 state-machine image) | ✓ | ✓ | Downloaded locally (79 KB) |
| Clipboard-pasted images (×2) — A10 architecture, General Description | ✓ | ✓ | Downloaded locally (60 KB + 84 KB) after defect fix |
| **Draw.io diagram — REQ 002 (state machine)** | rendered image only | **13 nodes + 6 edges as text** | **New capability** |
| **Draw.io diagram — REQ 005 (main flow)** | rendered image only | **~150 nodes + ~140 edges as text** | **New capability** |

---

## What the converter unlocks that the source does not expose

The two draw.io diagrams in this specification are the most information-dense artifacts on the page. Confluence stores them as binary files; the page itself surfaces them only as rendered images, which means a text-only RAG pipeline cannot read them at all.

The converter downloads the underlying `.drawio` file, decompresses it, and renders the diagram as a structured node-and-edge listing. **Sample excerpt** from the REQ 002 state machine:

```
Diagram: Page-1
Nodes:
  - Revive All wafer handling devices Flow
  - Automatic Revive Start
  - User manual operations
  - Error Type
  - Service
  - Revive Pass
  - Revive Failed
Edges:
  - Error Type -> Revive All wafer handling devices Flow
  - Revive All wafer handling devices Flow -> Service
  - Revive All wafer handling devices Flow -> User manual operations
  - User manual operations -> Revive All wafer handling devices Flow
```

The full REQ 005 main-flow diagram contributes ~290 such lines to the output. **None of that content was searchable before.**

---

## Defects found and fixed during verification

The verification process intentionally went beyond "did the tool finish without error." Three defects were identified and resolved before this report was finalized.

| Defect | Root cause | Resolution |
|---|---|---|
| Clipboard-pasted images failed to save (2/3 images missing in the first run) | Confluence stores Outlook-pasted images as attachments whose filenames contain `?` and `&` from the original Outlook URL. The utility was passing those filenames directly to the OS, and Windows refuses `?` in file paths, causing `open()` to fail silently | Filenames are now sanitized for filesystem use while preserving the original Confluence name for attachment-by-name matching. All 3 images now download |
| Internal Confluence page links rendered as plain text only | Cross-page link resolution was deferred from v0.1 | Added page-title-to-URL lookup against the v2 API with caching; resolved links now render as proper `[text](url)` markdown |
| Underline emphasis lost during conversion | Markdown has no native underline syntax | Underline is now preserved as `<u>...</u>`, which renders correctly in standard markdown viewers and is indexed as plain text by RAG embedders |

All three fixes were validated by re-running the conversion against the same source page. Output bundle is complete; **there are no remaining material gaps**.

---

## Risk assessment

| Risk | Severity | Status |
|---|---|---|
| Sensitive content leaking outside corporate boundary | Low | All processing is local; the utility downloads attachments to disk and does not call any external services |
| Stale output if source page is edited | Low | Re-running the utility takes < 30 seconds; can be scripted into a refresh job |
| Broken output if the source uses an unsupported macro type | Low | Unknown macros degrade gracefully — text inside is preserved; only the macro chrome is dropped |
| Authentication / proxy interference | Resolved | Uses the OS certificate trust store, so corporate HTTPS-inspecting proxies are handled transparently |

---

## Recommendation

The output is approved for ingestion into the RAG pipeline. The team should:

1. **Run the utility as the standard ingestion path** for image- and diagram-heavy specifications.
2. **Schedule a refresh** whenever the source page is updated; this is a one-command operation.
3. **Optionally annotate the two clipboard images** in `revive-all-wafer-handling-devices-rev-4.todo.md` with a 1-line description each. The image bytes are now downloaded locally — open them, write a sentence describing what they show, and replace the corresponding HTML comments in the main `.md` file. Without this step, the images are still embedded and viewable, but RAG retrieval will rank them lower because the embedder cannot read pixels.
4. **Track adoption** by extending the utility to a few more representative pages (one with PlantUML, one with screenshots, one with a code macro) and confirming the same coverage profile holds.

---

## Output bundle reference

```
output/revive-all-wafer-handling-devices-rev-4/
├── revive-all-wafer-handling-devices-rev-4.md       ← primary RAG input
├── revive-all-wafer-handling-devices-rev-4.todo.md  ← optional: 1-line descriptions for clipboard images
├── images/
│   ├── image-20260312-075456.png                    ← native attachment (79 KB)
│   ├── GetClipboardImage.ashx_Id=bd14c311…           ← clipboard image #1 (60 KB)
│   └── GetClipboardImage.ashx_Id=b3376404…           ← clipboard image #2 (84 KB)
└── diagrams/
    ├── Untitled Diagram-1771408147888.drawio        ← decoded for content
    └── Untitled Diagram-1772540250927.drawio        ← decoded for content
```
