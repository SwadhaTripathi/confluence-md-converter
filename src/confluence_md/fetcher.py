"""Confluence Cloud REST v2 client. Auth via HTTP Basic (email + API token)."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
from urllib.parse import urlparse, parse_qs

import requests
from requests.auth import HTTPBasicAuth


PAGE_ID_FROM_PATH = re.compile(r"/pages/(\d+)(?:/|$)")


@dataclass
class Attachment:
    id: str
    filename: str
    media_type: str
    download_url: str  # absolute


@dataclass
class Page:
    id: str
    title: str
    storage_xhtml: str


class ConfluenceClient:
    def __init__(self, base_url: str | None = None, email: str | None = None, token: str | None = None):
        self.base_url = (base_url or os.environ["CONFLUENCE_BASE_URL"]).rstrip("/")
        self.auth = HTTPBasicAuth(email or os.environ["CONFLUENCE_EMAIL"], token or os.environ["CONFLUENCE_API_TOKEN"])
        self.session = requests.Session()
        self.session.auth = self.auth
        self.session.headers.update({"Accept": "application/json"})

    def parse_page_id(self, url_or_id: str) -> str:
        if url_or_id.isdigit():
            return url_or_id
        parsed = urlparse(url_or_id)
        m = PAGE_ID_FROM_PATH.search(parsed.path)
        if m:
            return m.group(1)
        qs = parse_qs(parsed.query)
        if "pageId" in qs:
            return qs["pageId"][0]
        raise ValueError(f"Could not extract page ID from: {url_or_id!r}")

    def fetch_page(self, page_id: str) -> Page:
        r = self.session.get(
            f"{self.base_url}/wiki/api/v2/pages/{page_id}",
            params={"body-format": "storage"},
        )
        r.raise_for_status()
        data = r.json()
        return Page(
            id=str(data["id"]),
            title=data["title"],
            storage_xhtml=data["body"]["storage"]["value"],
        )

    def _absolute_url(self, path: str) -> str:
        """Resolve an API-returned link to an absolute URL.

        Confluence Cloud's `_links.download` is relative to the `/wiki/` base
        (e.g. `/download/attachments/...`), so we prepend `/wiki` for paths
        that don't already include it. Pagination links (`_links.next`) usually
        already include `/wiki/api/...`, so the prefix check handles them too.
        """
        if path.startswith(("http://", "https://")):
            return path
        if path.startswith("/wiki/"):
            return self.base_url + path
        if path.startswith("/"):
            return self.base_url + "/wiki" + path
        return self.base_url + "/wiki/" + path

    def list_attachments(self, page_id: str) -> list[Attachment]:
        results: list[Attachment] = []
        url = f"{self.base_url}/wiki/api/v2/pages/{page_id}/attachments"
        params = {"limit": 250}
        while url:
            r = self.session.get(url, params=params)
            r.raise_for_status()
            payload = r.json()
            for a in payload.get("results", []):
                results.append(Attachment(
                    id=str(a["id"]),
                    filename=a["title"],
                    media_type=a.get("mediaType", ""),
                    download_url=self._absolute_url(a["_links"]["download"]),
                ))
            next_link = payload.get("_links", {}).get("next")
            url = self._absolute_url(next_link) if next_link else None
            params = None
        return results

    def download_attachment(self, attachment: Attachment, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with self.session.get(attachment.download_url, stream=True) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=64 * 1024):
                    f.write(chunk)
        return dest

    def iter_pages_under(self, root_page_id: str) -> Iterator[str]:
        """Yield page IDs for the root and every descendant. Useful for recursive export."""
        yield root_page_id
        url = f"{self.base_url}/wiki/api/v2/pages/{root_page_id}/descendants"
        params = {"limit": 250}
        while url:
            r = self.session.get(url, params=params)
            r.raise_for_status()
            payload = r.json()
            for p in payload.get("results", []):
                yield str(p["id"])
            next_link = payload.get("_links", {}).get("next")
            url = (self.base_url + next_link) if next_link else None
            params = None
