# MCP markdown baseline (for comparison)

This is what Atlassian's MCP returns for the page **"Revive all wafer handling devices rev 4"** when asked for markdown. It is included here as the *baseline* — what you get with no tooling.

Notice three problems for RAG ingestion:

1. **Image references are `blob:https://media.staging.atl-paas.net/?...` URLs.** No filenames, no local paths, no alt text. RAG can't index them and you can't show them locally.
2. **No diagram sources extracted.** If the page has mermaid/plantuml/drawio macros, MCP renders them as opaque blobs.
3. **No sidecar TODO** — there's no list of which images need human description.

Our converter (`confluence-to-md`) addresses all three by reading the *storage format* directly via REST, downloading attachments locally, extracting macro source where possible, OCR'ing the rest, and emitting a sidecar TODO file.

---

## What MCP returned (truncated for brevity)

> Requirement divided to next steps :
>
> Comment : Need to add a complete flow for Revive All wafer handling from UX ( User interface ) Side.
>
> #### A10 Domains :
>
> Comment : Add a case when FI Pulling info from Platform and we lost communication. What should happened then.
>
> * In General FI Server will pull data from platform server but platform will not pull data from FI. So it means that FI Server will "Control" Platform in case of an error.
>
> ![](blob:https://media.staging.atl-paas.net/?type=file&localId=8c2f5472150b&id=5bef5599-e32c-4555-bd9b-acb21f8bef57&...)
>
> #### **REQ 001 - Safety flag**
>
> **General description**
>
> Safety flag ( Safety state)  will be turn to true according to error definitions below at **REQ 003.**
>
> Once this safety flag is turned to True System will move to "Halted" state per state machine.
>
> *(...page continues with 4 more sections, 5 images, multiple tables...)*

The full markdown is ~12 KB. The 5 images are all rendered as `blob:` URLs — useless for RAG, useless for local viewing.

## Compare to converter output

See `converter_output_demo.md` (in this folder) for what `confluence-to-md` produces against an equivalent storage-format input.
