from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from html import unescape
from pathlib import Path
from urllib.request import Request, urlopen


FEED_URL = "https://blog.samaltman.com/posts.atom"
SUBJECT_DIR = Path("data/sam_altman")
SOURCES_DIR = SUBJECT_DIR / "sources"
USER_AGENT = "Mozilla/5.0 (compatible; CodexDataFetcher/1.0)"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


def fetch(url: str) -> str:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")


def html_to_text(fragment: str) -> str:
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", "", fragment)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p\s*>", "\n\n", text)
    text = re.sub(r"(?i)</div\s*>", "\n", text)
    text = re.sub(r"(?i)</li\s*>", "\n", text)
    text = re.sub(r"(?i)<li\b[^>]*>", "- ", text)
    text = re.sub(r"(?i)</h[1-6]\s*>", "\n\n", text)
    text = re.sub(r"(?is)<[^>]+>", "", text)
    text = unescape(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def slugify(url: str) -> str:
    slug = url.rstrip("/").rsplit("/", 1)[-1]
    slug = re.sub(r"[^a-z0-9]+", "_", slug.lower()).strip("_")
    return slug


def main(limit: int | None = None) -> int:
    SUBJECT_DIR.mkdir(parents=True, exist_ok=True)
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)

    root = ET.fromstring(fetch(FEED_URL))
    entries = root.findall("atom:entry", ATOM_NS)
    if limit is not None:
        entries = entries[:limit]

    manifest_sources = []
    for idx, entry in enumerate(entries, start=1):
        title = (entry.findtext("atom:title", default="", namespaces=ATOM_NS) or "").strip()
        published = (
            entry.findtext("atom:published", default="", namespaces=ATOM_NS)
            or entry.findtext("atom:updated", default="", namespaces=ATOM_NS)
        ).strip()
        date = published[:10] if published else ""

        link_el = entry.find("atom:link[@rel='alternate']", ATOM_NS)
        if link_el is None:
            link_el = entry.find("atom:link", ATOM_NS)
        if link_el is None or "href" not in link_el.attrib:
            raise ValueError(f"Missing link for entry {title}")
        url = link_el.attrib["href"]

        content_html = entry.findtext("atom:content", default="", namespaces=ATOM_NS)
        content_text = html_to_text(content_html)
        if not content_text:
            raise ValueError(f"Empty content for entry {title}")

        filename = f"{idx:03d}_{slugify(url)}.txt"
        body = (
            f"Title: {title}\n"
            f"Date: {date}\n"
            f"URL: {url}\n\n"
            f"{content_text}\n"
        )
        (SOURCES_DIR / filename).write_text(body, encoding="utf-8")

        manifest_sources.append(
            {
                "id": f"src_{idx:03d}",
                "type": "blog",
                "date": date,
                "file": f"sources/{filename}",
                "context": title,
            }
        )
        print(f"[{idx}/{len(entries)}] saved {filename}")

    manifest = {
        "subject": "Sam Altman",
        "description": "Original-text corpus of Sam Altman's official blog posts from his Posthaven feed.",
        "sources": manifest_sources,
    }
    (SUBJECT_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"wrote {len(manifest_sources)} sources to {SUBJECT_DIR}")
    return 0


if __name__ == "__main__":
    limit = None
    if len(sys.argv) > 1:
        limit = int(sys.argv[1])
    raise SystemExit(main(limit))
