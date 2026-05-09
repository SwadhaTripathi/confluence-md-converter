"""Decode a Confluence drawio attachment (.drawio file) into a RAG-friendly text summary.

A .drawio file is XML. The outer <mxfile> contains one or more <diagram> elements; each
<diagram> either contains an <mxGraphModel> directly (uncompressed) or a base64-encoded
deflate-compressed URL-encoded payload (compressed).

We extract:
  - vertex labels (the text on each node)
  - edges as "source-label -> target-label (edge-label)"

The output reads like a structured graph description and embeds well even though no
visual rendering ever happens.
"""
from __future__ import annotations

import base64
import html
import re
import xml.etree.ElementTree as ET
import zlib
from urllib.parse import unquote


def _decompress_payload(b64_payload: str) -> str | None:
    """Inverse of drawio's compress: base64 decode → raw deflate → URL-decode."""
    try:
        raw = base64.b64decode(b64_payload.strip())
        inflated = zlib.decompress(raw, -zlib.MAX_WBITS)
        return unquote(inflated.decode("utf-8"))
    except Exception:
        return None


def _clean_label(html_value: str) -> str:
    """Drawio labels can contain HTML markup and entities. Reduce to plain text."""
    if not html_value:
        return ""
    text = re.sub(r"<[^>]+>", " ", html_value)
    text = html.unescape(text)
    return " ".join(text.split())


def _summarize_graph(graph: ET.Element, *, name: str = "") -> str:
    cells = graph.findall(".//mxCell")
    nodes: dict[str, str] = {}
    edges: list[tuple[str, str, str]] = []

    for cell in cells:
        cell_id = cell.get("id", "")
        label = _clean_label(cell.get("value", "") or "")
        if cell.get("vertex") == "1":
            nodes[cell_id] = label
        elif cell.get("edge") == "1":
            src = cell.get("source", "")
            tgt = cell.get("target", "")
            edges.append((src, tgt, label))

    lines: list[str] = []
    if name:
        lines.append(f"Diagram: {name}")
    labelled = [lbl for lbl in nodes.values() if lbl]
    if labelled:
        lines.append("Nodes:")
        for lbl in labelled:
            lines.append(f"  - {lbl}")
    if edges:
        lines.append("Edges:")
        for src, tgt, edge_label in edges:
            src_lbl = nodes.get(src, "?") or "?"
            tgt_lbl = nodes.get(tgt, "?") or "?"
            arrow = f"  - {src_lbl} -> {tgt_lbl}"
            if edge_label:
                arrow += f" ({edge_label})"
            lines.append(arrow)

    return "\n".join(lines)


def summarize(xml_text: str) -> str:
    """Convert a .drawio file's XML content into a multi-line text summary.
    Returns empty string if the input cannot be parsed or contains nothing useful."""
    if not xml_text or not xml_text.strip():
        return ""

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return ""

    if root.tag == "mxGraphModel":
        return _summarize_graph(root)

    diagrams = root.findall(".//diagram")
    if not diagrams:
        return ""

    summaries: list[str] = []
    for diagram in diagrams:
        name = diagram.get("name", "")
        graph = diagram.find("mxGraphModel")
        if graph is None:
            payload = (diagram.text or "").strip()
            if not payload:
                continue
            decoded = _decompress_payload(payload)
            if decoded is None:
                continue
            try:
                graph = ET.fromstring(decoded)
            except ET.ParseError:
                continue
            if graph.tag != "mxGraphModel":
                inner = graph.find(".//mxGraphModel")
                if inner is None:
                    continue
                graph = inner
        s = _summarize_graph(graph, name=name)
        if s.strip():
            summaries.append(s)

    return "\n\n".join(summaries)
