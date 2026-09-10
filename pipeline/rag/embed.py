"""
pipeline/rag/embed.py
=====================
Step 3: Generate sentence embeddings for all chunks (laptop/server only).

Input:  data/chunks/*.json
Output: data/embeddings/*.npy   (numpy float32 arrays, one per source file)
        data/embeddings/index.faiss  (FAISS flat L2 index over all chunks)
        data/embeddings/metadata.json (chunk metadata aligned with FAISS rows)

This step runs on a laptop with 8 GB+ RAM. The embeddings are NOT shipped
to the mobile app — the app uses keyword (LIKE) matching only.
Embeddings are used for backend semantic search (optional online mode).

Model: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
  - Free, open-source
  - Supports English, Urdu, and Roman Urdu (via multilingual training)
  - ~118 MB download, runs on CPU in ~2-4 min for 500 chunks

Dependencies: sentence-transformers, faiss-cpu, numpy
"""

import json
import sys
import time
from pathlib import Path

import numpy as np

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    print("ERROR: sentence-transformers not installed.")
    print("Run: pip install sentence-transformers")
    sys.exit(1)

try:
    import faiss
except ImportError:
    print("ERROR: faiss-cpu not installed.")
    print("Run: pip install faiss-cpu")
    sys.exit(1)

# ── Config ─────────────────────────────────────────────────────────────────────
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
BATCH_SIZE = 64

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
CHUNKS_DIR = ROOT / "data" / "chunks"
EMB_DIR = ROOT / "data" / "embeddings"
EMB_DIR.mkdir(parents=True, exist_ok=True)


def load_all_chunks() -> list[dict]:
    """Load and flatten all chunks from all source files."""
    all_chunks = []
    for fp in sorted(CHUNKS_DIR.glob("*.json")):
        with open(fp, encoding="utf-8") as f:
            chunks = json.load(f)
        all_chunks.extend(chunks)
    return all_chunks


def main():
    chunks = load_all_chunks()
    if not chunks:
        print(f"No chunk files found in {CHUNKS_DIR}. Run chunk.py first.")
        sys.exit(1)

    print(f"Loaded {len(chunks)} chunks from {CHUNKS_DIR}")
    print(f"Loading model: {MODEL_NAME}")

    model = SentenceTransformer(MODEL_NAME)
    dim = model.get_sentence_embedding_dimension()
    print(f"Embedding dimension: {dim}")

    texts = [c["chunk_text"] for c in chunks]

    print(f"Encoding {len(texts)} chunks (batch_size={BATCH_SIZE})…")
    t0 = time.time()
    embeddings = model.encode(
        texts,
        batch_size=BATCH_SIZE,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    elapsed = time.time() - t0
    print(f"Encoding done in {elapsed:.1f}s  shape={embeddings.shape}")

    # Save numpy array
    npy_path = EMB_DIR / "all_embeddings.npy"
    np.save(str(npy_path), embeddings.astype(np.float32))
    print(f"Saved embeddings: {npy_path}")

    # Build FAISS index (flat cosine via normalised dot product)
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings.astype(np.float32))
    faiss_path = EMB_DIR / "index.faiss"
    faiss.write_index(index, str(faiss_path))
    print(f"FAISS index: {faiss_path}  ({index.ntotal} vectors)")

    # Save aligned metadata
    meta = [
        {
            "row": i,
            "chunk_id": c["chunk_id"],
            "source_org": c["source_org"],
            "doc_title": c["doc_title"],
            "pub_date": c["pub_date"],
            "language": c["language"],
            "evidence_level": c["evidence_level"],
        }
        for i, c in enumerate(chunks)
    ]
    meta_path = EMB_DIR / "metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"Metadata: {meta_path}")

    # Summary
    lang_counts: dict[str, int] = {}
    for c in chunks:
        lang_counts[c["language"]] = lang_counts.get(c["language"], 0) + 1
    print("\n── Embedding summary ──")
    for lang, count in sorted(lang_counts.items()):
        print(f"  {lang}: {count} chunks")
    print(f"  Total: {len(chunks)} chunks, {dim}-d embeddings")


if __name__ == "__main__":
    main()
