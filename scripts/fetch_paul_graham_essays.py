from __future__ import annotations

import json
import re
import sys
from html import unescape
from pathlib import Path
from urllib.request import Request, urlopen


BASE_URL = "https://paulgraham.com/"
INDEX_URL = f"{BASE_URL}articles.html"
SUBJECT_DIR = Path("data/paul_graham")
SOURCES_DIR = SUBJECT_DIR / "sources"
USER_AGENT = "Mozilla/5.0 (compatible; CodexDataFetcher/1.0)"
IGNORE_HREFS = {
    "index.html",
    "articles.html",
    "books.html",
    "arc.html",
    "bel.html",
    "lisp.html",
    "antispam.html",
    "kedrosky.html",
    "faq.html",
    "raq.html",
    "quo.html",
    "rss.html",
    "bio.html",
}


def fetch(url: str) -> str:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")


def html_to_text(fragment: str) -> str:
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", "", fragment)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p\s*>", "\n\n", text)
    text = re.sub(r"(?i)</tr\s*>", "\n", text)
    text = re.sub(r"(?i)</td\s*>", "\n", text)
    text = re.sub(r"(?i)</font\s*>", "\n", text)
    text = re.sub(r"(?is)<[^>]+>", "", text)
    text = unescape(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def essay_links(limit: int) -> list[tuple[str, str]]:
    html = fetch(INDEX_URL)
    matches = re.findall(r'<a href="([^"]+\.html)">([^<]+)</a>', html, flags=re.IGNORECASE)
    links: list[tuple[str, str]] = []
    seen = set()
    for href, title in matches:
        href = href.strip()
        title = unescape(title).strip()
        if href in IGNORE_HREFS:
            continue
        if href.startswith("http"):
            continue
        if href in seen:
            continue
        seen.add(href)
        links.append((href, title))
        if len(links) >= limit:
            break
    return links


def extract_date(text: str) -> str:
    match = re.search(
        r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b",
        text,
    )
    if not match:
        return ""
    month, year = match.group(0).split()
    month_num = {
        "January": "01",
        "February": "02",
        "March": "03",
        "April": "04",
        "May": "05",
        "June": "06",
        "July": "07",
        "August": "08",
        "September": "09",
        "October": "10",
        "November": "11",
        "December": "12",
    }[month]
    return f"{year}-{month_num}"


def extract_body(html: str, title: str) -> str:
    text = html_to_text(html)
    start = text.find(title)
    if start != -1:
        text = text[start + len(title):].strip()
    text = re.sub(r"^-->\s*", "", text)
    return text


def main(limit: int = 32) -> int:
    SUBJECT_DIR.mkdir(parents=True, exist_ok=True)
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)

    links = essay_links(limit)
    manifest_sources = []
    for idx, (href, title_hint) in enumerate(links, start=1):
        url = href if href.startswith("http") else f"{BASE_URL}{href}"
        html = fetch(url)
        title_match = re.search(r"(?is)<title>(.*?)</title>", html)
        title = html_to_text(title_match.group(1)) if title_match else title_hint
        body_text = extract_body(html, title)
        date = extract_date(body_text)
        filename = f"{idx:03d}_{re.sub(r'[^a-z0-9]+', '_', href.lower()).strip('_')}.txt"
        content = (
            f"Title: {title}\n"
            f"Date: {date}\n"
            f"URL: {url}\n\n"
            f"{body_text}\n"
        )
        (SOURCES_DIR / filename).write_text(content, encoding="utf-8")
        manifest_sources.append(
            {
                "id": f"src_{idx:03d}",
                "type": "essay",
                "date": date,
                "file": f"sources/{filename}",
                "context": title,
            }
        )
        print(f"[{idx}/{len(links)}] saved {filename}")

    manifest = {
        "subject": "Paul Graham",
        "description": "Original-text corpus of Paul Graham essays from his official site.",
        "sources": manifest_sources,
    }
    (SUBJECT_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"wrote {len(manifest_sources)} sources to {SUBJECT_DIR}")
    return 0


if __name__ == "__main__":
    limit = 32
    if len(sys.argv) > 1:
        limit = int(sys.argv[1])
    raise SystemExit(main(limit))
