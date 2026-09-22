"""
Phase 1: PDF ingestion + parsing + chunking.

Reads all PDFs in docs/, extracts text page by page, splits into overlapping
chunks, and writes a single JSON file (docs/chunks.json) that downstream
phases (embeddings, retrieval, UI) consume.
"""
import json
import re
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "docs"
OUT_PATH = DOCS_DIR / "chunks.json"

CHUNK_SIZE = 1200       # characters per chunk
CHUNK_OVERLAP = 200     # characters of overlap between consecutive chunks

# Source metadata: authority hierarchy established in Phase 0.
SOURCE_META = {
    "master_plan_2026.pdf": {
        "title": "Second Master Plan for Chennai Metropolitan Area, 2026",
        "authority": "primary",
        "topic": "land use, zoning, spatial strategy",
    },
    "tncdrbr_2019.pdf": {
        "title": "Tamil Nadu Combined Development and Building Rules, 2019",
        "authority": "primary",
        "topic": "building regulations, FSI, setbacks, development control",
    },
    "dcr_2004.pdf": {
        "title": "Development Control Rules for CMA, 2004",
        "authority": "superseded",
        "topic": "legacy development control rules (superseded by TNCDRBR 2019)",
    },
}


def clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, size: int, overlap: int):
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + size, n)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == n:
            break
        start = end - overlap
    return chunks


def extract_pdf(path: Path):
    """Yield (page_number, text) for each page in the PDF."""
    reader = PdfReader(str(path))
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as e:
            print(f"  ! page {i} extraction failed: {e}")
            text = ""
        yield i, clean_text(text)


def main():
    pdf_files = sorted(DOCS_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDFs found in {DOCS_DIR}")
        return

    all_chunks = []
    chunk_id = 0

    for pdf_path in pdf_files:
        fname = pdf_path.name
        meta = SOURCE_META.get(fname, {"title": fname, "authority": "unknown", "topic": ""})
        print(f"Processing {fname} ...")

        page_count = 0
        char_count = 0
        for page_num, page_text in extract_pdf(pdf_path):
            page_count += 1
            if not page_text:
                continue
            char_count += len(page_text)
            for c in chunk_text(page_text, CHUNK_SIZE, CHUNK_OVERLAP):
                all_chunks.append({
                    "id": chunk_id,
                    "source_file": fname,
                    "source_title": meta["title"],
                    "authority": meta["authority"],
                    "topic": meta["topic"],
                    "page": page_num,
                    "text": c,
                })
                chunk_id += 1

        print(f"  pages: {page_count}, chars extracted: {char_count}")

    DOCS_DIR.mkdir(exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=1)

    print(f"\nWrote {len(all_chunks)} chunks from {len(pdf_files)} PDFs -> {OUT_PATH}")


if __name__ == "__main__":
    main()
