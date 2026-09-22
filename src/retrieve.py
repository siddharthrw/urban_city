"""
Phase 2: Retrieval layer.

Loads chunks.json + embeddings.npy and provides a `search(query, k)` function
that returns the top-k most relevant chunks via cosine similarity, with a
small authority boost so primary (current) regulations outrank superseded
ones (DCR 2004) when scores are close.
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
AUTHORITY_BOOST = {"primary": 0.05, "superseded": 0.0, "unknown": 0.0}

_model = None
_chunks = None
_embeddings = None


def _load():
    global _model, _chunks, _embeddings
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    if _chunks is None:
        with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
            _chunks = json.load(f)
    if _embeddings is None:
        _embeddings = np.load(EMB_PATH)


def search(query: str, k: int = 5):
    _load()
    q_emb = _model.encode([query], normalize_embeddings=True)[0]
    sims = _embeddings @ q_emb  # cosine similarity (both normalized)

    boosted = sims + np.array(
        [AUTHORITY_BOOST.get(c["authority"], 0.0) for c in _chunks]
    )

    top_idx = np.argsort(-boosted)[:k]
    results = []
    for i in top_idx:
        c = _chunks[i]
        results.append({
            "score": float(sims[i]),
            "source_file": c["source_file"],
            "source_title": c["source_title"],
            "authority": c["authority"],
            "page": c["page"],
            "text": c["text"],
        })
    return results


if __name__ == "__main__":
    import sys

    query = " ".join(sys.argv[1:]) or "What is the maximum FSI for residential buildings?"
    print(f"Query: {query}\n")
    for r in search(query, k=5):
        print(f"[{r['score']:.3f}] {r['source_file']} (p.{r['page']}, {r['authority']})")
        print(r["text"][:300].replace("\n", " "))
        print()
