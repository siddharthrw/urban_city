"""
Phase 2: Embeddings + vector store.

Loads docs/chunks.json, embeds each chunk's text with a local sentence-transformer
model, and saves the embedding matrix (docs/embeddings.npy) alongside the chunks
so retrieval never needs to re-embed the corpus.
"""
import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "docs"
CHUNKS_PATH = DOCS_DIR / "chunks.json"
EMB_PATH = DOCS_DIR / "embeddings.npy"

MODEL_NAME = "all-MiniLM-L6-v2"


def main():
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    texts = [c["text"] for c in chunks]
    print(f"Embedding {len(texts)} chunks with {MODEL_NAME} ...")

    model = SentenceTransformer(MODEL_NAME)
    embeddings = model.encode(
        texts,
        batch_size=64,
        show_progress_bar=True,
        normalize_embeddings=True,  # so cosine similarity = dot product
    )
    embeddings = np.asarray(embeddings, dtype=np.float32)

    np.save(EMB_PATH, embeddings)
    print(f"Saved embeddings {embeddings.shape} -> {EMB_PATH}")


if __name__ == "__main__":
    main()
