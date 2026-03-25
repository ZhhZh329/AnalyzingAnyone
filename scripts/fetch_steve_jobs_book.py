from __future__ import annotations

import json
import re
import sys
from html import unescape
from pathlib import Path
from urllib.request import Request, urlopen


BOOK_URL = "https://book.stevejobsarchive.com/"
SUBJECT_DIR = Path("data/steve_jobs")
SOURCES_DIR = SUBJECT_DIR / "sources"
USER_AGENT = "Mozilla/5.0 (compatible; CodexDataFetcher/1.0)"


def fetch(url: str) -> str:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")


def html_to_text(html: str) -> str:
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", "", html)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p\s*>", "\n\n", text)
    text = re.sub(r"(?i)</div\s*>", "\n", text)
    text = re.sub(r"(?i)</h[1-6]\s*>", "\n\n", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = unescape(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_book_text(raw_text: str) -> str:
    start = raw_text.find("Preface:")
    end = raw_text.rfind("Credits")
    if start == -1:
        raise ValueError("Could not find Preface marker in book text")
    if end == -1 or end <= start:
        end = len(raw_text)
    text = raw_text[start:end].strip()
    text = text.replace("✂", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def chunk_paragraphs(text: str, count: int) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) < count:
        raise ValueError("Not enough paragraphs to chunk the book")

    total_len = sum(len(p) for p in paragraphs)
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    used = 0

    for idx, paragraph in enumerate(paragraphs):
        remaining_paragraphs = len(paragraphs) - idx
        remaining_chunks = count - len(chunks)
        remaining_len = total_len - used
        target = remaining_len / remaining_chunks

        current.append(paragraph)
        current_len += len(paragraph)
        used += len(paragraph)

        enough_text = current_len >= target
        enough_paragraphs_left = remaining_paragraphs >= remaining_chunks
        if enough_text and enough_paragraphs_left and len(chunks) < count - 1:
            chunks.append("\n\n".join(current).strip())
            current = []
            current_len = 0

    if current:
        chunks.append("\n\n".join(current).strip())

    if len(chunks) != count:
        raise ValueError(f"Expected {count} chunks, got {len(chunks)}")
    return chunks


def main(count: int = 32) -> int:
    SUBJECT_DIR.mkdir(parents=True, exist_ok=True)
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)

    html = fetch(BOOK_URL)
    raw_text = html_to_text(html)
    book_text = clean_book_text(raw_text)
    chunks = chunk_paragraphs(book_text, count)

    manifest_sources = []
    for idx, chunk in enumerate(chunks, start=1):
        filename = f"{idx:03d}_make_something_wonderful_chunk_{idx:02d}.txt"
        content = (
            "Title: Make Something Wonderful\n"
            f"Date: 2023\n"
            f"URL: {BOOK_URL}\n"
            f"Chunk: {idx}/{count}\n\n"
            f"{chunk}\n"
        )
        (SOURCES_DIR / filename).write_text(content, encoding="utf-8")
        manifest_sources.append(
            {
                "id": f"src_{idx:03d}",
                "type": "book_excerpt",
                "date": "2023",
                "file": f"sources/{filename}",
                "context": f"Make Something Wonderful chunk {idx:02d}",
            }
        )
        print(f"[{idx}/{count}] saved {filename}")

    manifest = {
        "subject": "Steve Jobs",
        "description": "Original-text corpus chunked from the official Steve Jobs Archive web book Make Something Wonderful.",
        "sources": manifest_sources,
    }
    (SUBJECT_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"wrote {len(manifest_sources)} sources to {SUBJECT_DIR}")
    return 0


if __name__ == "__main__":
    count = 32
    if len(sys.argv) > 1:
        count = int(sys.argv[1])
    raise SystemExit(main(count))
