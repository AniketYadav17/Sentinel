"""Rule-aware chunker for FCA Handbook provisions: one chunk per rule/guidance.

Input is the provision dicts returned by the handbook JSON API (see ingest.py).
Text is parsed from the ``contentType`` HTML rather than ``contentText`` because
the plain text flattens nested (a)/(b) sub-paragraphs and drops tables.
"""

from html.parser import HTMLParser

_DESIGNATION = {"Rules": "R", "Guidance": "G"}


class _TextExtractor(HTMLParser):
    """Flatten handbook HTML to text: one line per list item / table row."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in ("li", "tr", "div", "br"):
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th"):
            self.parts.append(" | ")
        elif tag == "p":
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    lines = (" ".join(line.split()).removesuffix(" |") for line in "".join(parser.parts).splitlines())
    return "\n".join(line for line in lines if line)


def chunk_provisions(provisions: list[dict], source_url: str, retrieved_on: str) -> list[dict]:
    """One chunk per provision, section title prefixed to the text for context."""
    chunks = []
    for prov in provisions:
        if prov.get("isDeleted"):
            continue
        rule_id = prov["provisionName"]  # e.g. "CONC 3.3.1"
        sourcebook, ref = rule_id.split(" ", 1)
        designation = _DESIGNATION.get(prov["provisionType"], prov["provisionType"][:1])
        text = html_to_text(prov["contentType"] or "")
        if not text:
            raise ValueError(f"empty HTML content for provision {rule_id}")
        chunks.append(
            {
                "sourcebook": sourcebook,
                "chapter": ref.split(".", 1)[0],
                "section": rule_id.rsplit(".", 1)[0],
                "rule_id": rule_id,
                "designation": designation,
                "text": f"{rule_id} {designation}\n{prov['sectionName']}\n{text}",
                "source_url": source_url,
                "retrieved_on": retrieved_on,
            }
        )
    return chunks
