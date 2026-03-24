"""
loader.py — Read data/{subject}/ folder into a dict.

Usage:
    data = load(Path("data/elon_musk"))
    # data = {"subject": "Elon Musk", "sources": [...]}
"""

import json
from pathlib import Path


def load(data_dir: Path) -> dict:
    """
    Read manifest.json + all source files.
    Returns a SubjectData-compatible dict.
    """
    manifest_path = data_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest.json not found in {data_dir}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    sources = []
    for entry in manifest["sources"]:
        file_path = data_dir / entry["file"]
        if not file_path.exists():
            raise FileNotFoundError(f"Source file not found: {file_path}")

        source = {
            "id": entry["id"],
            "type": entry["type"],
            "date": entry["date"],
            "content": file_path.read_text(encoding="utf-8").strip(),
        }
        # Carry over any extra fields from manifest (e.g. context)
        for k, v in entry.items():
            if k not in source and k != "file":
                source[k] = v

        sources.append(source)

    return {
        "subject": manifest["subject"],
        "sources": sources,
    }
