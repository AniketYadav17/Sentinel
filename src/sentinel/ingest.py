"""Fetch FCA Handbook chapters from the open handbook JSON API and write chunks.

Usage: python -m sentinel.ingest CONC 3  ->  data/chunks/conc3.jsonl
"""

import json
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

from sentinel.chunk import chunk_provisions

API = "https://api-handbook.fca.org.uk/Handbook/GetAllHandBookProvisionsSortedOrderByChapter/{chapter_id}"
HEADERS = {"User-Agent": "sentinel-research/0.1", "Accept": "application/json"}
SLEEP_SECONDS = 1.0  # politeness: ~1 request/second, sequential only


def fetch_chapter(chapter_id: str) -> dict:
    """Fetch one chapter's provisions JSON. Single seam — swap here to change source."""
    time.sleep(SLEEP_SECONDS)
    url = API.format(chapter_id=chapter_id)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if payload.get("Error") or not payload.get("Result"):
        raise RuntimeError(f"FCA API error for {url}: {payload.get('Error')!r}")
    return payload["Result"]


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit("usage: python -m sentinel.ingest SOURCEBOOK CHAPTER  (e.g. CONC 3)")
    sourcebook, chapter = sys.argv[1].upper(), sys.argv[2]
    chapter_id = f"{sourcebook}{chapter}".lower()  # API ids are all-lowercase, e.g. conc5a
    result = fetch_chapter(chapter_id)
    chunks = chunk_provisions(
        result["provisions"],
        source_url=API.format(chapter_id=chapter_id),
        retrieved_on=date.today().isoformat(),
    )
    out = Path(__file__).parents[2] / "data" / "chunks" / f"{chapter_id}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    sections = len({c["section"] for c in chunks})
    print(f"{sourcebook} {chapter}: {len(chunks)} chunks, {sections} sections -> {out}")


if __name__ == "__main__":
    main()
