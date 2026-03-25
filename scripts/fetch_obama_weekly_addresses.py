from __future__ import annotations

import json
import re
import sys
from html import unescape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_URL = "https://obamawhitehouse.archives.gov"
ARCHIVE_PATH = "/briefing-room/weekly-address"
SUBJECT_DIR = Path("data/barack_obama")
SOURCES_DIR = SUBJECT_DIR / "sources"
USER_AGENT = "Mozilla/5.0 (compatible; CodexDataFetcher/1.0)"


def fetch(url: str) -> str:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")


def extract_div_by_class(html: str, class_fragment: str) -> str | None:
    pattern = re.compile(
        rf'<div\b[^>]*class="[^"]*{re.escape(class_fragment)}[^"]*"[^>]*>',
        re.IGNORECASE,
    )
    match = pattern.search(html)
    if not match:
        return None

    tag_pattern = re.compile(r"<div\b[^>]*>|</div>", re.IGNORECASE)
    depth = 1
    for tag_match in tag_pattern.finditer(html, match.end()):
        token = tag_match.group(0).lower()
        if token.startswith("<div"):
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                return html[match.start():tag_match.end()]
    return None


def html_to_text(fragment: str) -> str:
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", "", fragment)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p\s*>", "\n\n", text)
    text = re.sub(r"(?i)</div\s*>", "\n", text)
    text = re.sub(r"(?i)</h[1-6]\s*>", "\n\n", text)
    text = re.sub(r"(?is)<[^>]+>", "", text)
    text = unescape(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_title(html: str) -> str:
    match = re.search(r"(?is)<h1[^>]*>(.*?)</h1>", html)
    if not match:
        raise ValueError("Could not find page title")
    return html_to_text(match.group(1))


def extract_transcript(html: str) -> str:
    for class_fragment in (
        "field-name-field-transcript",
        "field-name-field-forall-body",
        "field-name-body",
    ):
        block = extract_div_by_class(html, class_fragment)
        if block:
            text = html_to_text(block)
            if text:
                return text
    raise ValueError("Could not find transcript/body block")


def weekly_archive_links() -> list[str]:
    links: list[str] = []
    seen = set()

    for page in range(44):
        suffix = f"{ARCHIVE_PATH}?page={page}" if page else ARCHIVE_PATH
        html = fetch(f"{BASE_URL}{suffix}")
        page_links = re.findall(r'href="(/the-press-office/\d{4}/\d{2}/\d{2}/[^"]+)"', html)
        for link in page_links:
            slug = link.rsplit("/", 1)[-1]
            if not slug.startswith("weekly-address-"):
                continue
            if "mensaje-semanal" in slug:
                continue
            if link in seen:
                continue
            seen.add(link)
            links.append(link)
    return links


def evenly_sample(items: list[str], limit: int) -> list[str]:
    if len(items) <= limit:
        return items[:]
    indices = sorted({round(i * (len(items) - 1) / (limit - 1)) for i in range(limit)})
    sampled = [items[i] for i in indices]
    while len(sampled) < limit:
        sampled.append(items[len(sampled)])
    return sampled[:limit]


def filename_from_url(idx: int, url_path: str) -> str:
    slug = url_path.rsplit("/", 1)[-1]
    slug = re.sub(r"[^a-z0-9]+", "_", slug.lower()).strip("_")
    return f"{idx:03d}_{slug}.txt"


def iso_date_from_url(url_path: str) -> str:
    match = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", url_path)
    if not match:
        raise ValueError(f"Could not infer date from {url_path}")
    return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"


def main(limit: int = 32) -> int:
    SUBJECT_DIR.mkdir(parents=True, exist_ok=True)
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)

    all_links = weekly_archive_links()
    if not all_links:
        raise RuntimeError("No weekly address links found")

    # Archive pages are newest first; reverse before sampling so the result spans
    # the presidency in chronological order.
    selected = evenly_sample(list(reversed(all_links)), limit)

    manifest_sources = []
    success = 0
    failures: list[tuple[str, str]] = []

    for url_path in selected:
        full_url = f"{BASE_URL}{url_path}"
        try:
            html = fetch(full_url)
            title = clean_title(html)
            transcript = extract_transcript(html)
            date = iso_date_from_url(url_path)
            success += 1
            filename = filename_from_url(success, url_path)
            file_path = SOURCES_DIR / filename
            body = (
                f"Title: {title}\n"
                f"Date: {date}\n"
                f"URL: {full_url}\n\n"
                f"{transcript}\n"
            )
            file_path.write_text(body, encoding="utf-8")
            manifest_sources.append(
                {
                    "id": f"src_{success:03d}",
                    "type": "speech",
                    "date": date,
                    "file": f"sources/{filename}",
                    "context": title,
                }
            )
            print(f"[{success}/{limit}] saved {filename}")
        except (ValueError, HTTPError, URLError, TimeoutError) as exc:
            failures.append((full_url, str(exc)))
            print(f"[skip] {full_url} :: {exc}", file=sys.stderr)

        if success >= limit:
            break

    manifest = {
        "subject": "Barack Obama",
        "description": "Original-text corpus of Barack Obama weekly addresses drawn from the Obama White House archive.",
        "sources": manifest_sources,
    }
    (SUBJECT_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"wrote {success} sources to {SUBJECT_DIR}")
    if failures:
        print(f"skipped {len(failures)} pages", file=sys.stderr)
    return 0 if success else 1


if __name__ == "__main__":
    limit = 32
    if len(sys.argv) > 1:
        limit = int(sys.argv[1])
    raise SystemExit(main(limit))
