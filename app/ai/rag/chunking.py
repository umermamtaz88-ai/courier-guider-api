import re


SECTION_MARKERS = [
    "scope",
    "eligibility",
    "fee",
    "exceptions",
    "procedure",
    "deadline",
    "contact",
    "returns",
    "refund",
    "claim",
    "cod",
    "settlement",
]


def semantic_chunk(text: str, max_chars: int = 900) -> list[dict]:
    """Chunk by sections/paragraphs instead of blind fixed token windows."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[dict] = []
    buffer = ""
    section_title: str | None = None

    for para in paragraphs:
        lower = para.lower()
        for marker in SECTION_MARKERS:
            if lower.startswith(marker + ":") or lower.startswith(marker + " "):
                if buffer:
                    chunks.append({"content": buffer.strip(), "section_title": section_title})
                    buffer = ""
                section_title = marker
                break

        if len(buffer) + len(para) + 2 > max_chars and buffer:
            chunks.append({"content": buffer.strip(), "section_title": section_title})
            buffer = para
        else:
            buffer = f"{buffer}\n\n{para}".strip() if buffer else para

    if buffer:
        chunks.append({"content": buffer.strip(), "section_title": section_title})

    if not chunks and text.strip():
        for i in range(0, len(text), max_chars):
            chunks.append({"content": text[i : i + max_chars], "section_title": None})

    return chunks
