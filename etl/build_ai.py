#!/usr/bin/env python3
"""
Semantic index for AI search and recommendations (runs after build_db.py).

Latent Semantic Analysis: TF-IDF (unigrams + bigrams) -> truncated SVD (256 dims) -> unit vectors.
Runs offline on a laptop in under a minute, no GPU or model download. The interface (embed a query,
nearest neighbours) is the same one a transformer embedding model would use, so bge-m3 can replace it
later without touching the API.

    python etl/build_ai.py   ->  db/ai/{vectors.npy, ids.json, model.joblib}
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import duckdb
import joblib
import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import Normalizer

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "db" / "lpip.duckdb"
OUT = ROOT / "db" / "ai"
DIMS = 256


def main() -> None:
    t0 = time.time()
    con = duckdb.connect(str(DB), read_only=True)
    docs = con.execute("""
        SELECT evidence_id, coalesce(title, '') || '. ' || coalesce(title, '') || '. ' || coalesce(abstract, '') AS text
        FROM evidence_item ORDER BY evidence_id""").fetchall()
    ids = [d[0] for d in docs]
    texts = [d[1] for d in docs]
    lsa = make_pipeline(
        TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=2, max_df=0.5, sublinear_tf=True,
                        max_features=120_000, token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z-]{2,}\b"),
        TruncatedSVD(n_components=DIMS, random_state=7),
        Normalizer(copy=False),
    )
    vecs = lsa.fit_transform(texts).astype(np.float32)
    OUT.mkdir(parents=True, exist_ok=True)
    np.save(OUT / "vectors.npy", vecs)
    (OUT / "ids.json").write_text(json.dumps(ids))
    joblib.dump(lsa, OUT / "model.joblib")
    ev = lsa.named_steps["truncatedsvd"].explained_variance_ratio_.sum()
    print(f"{len(ids):,} documents -> {DIMS}-dim semantic vectors (explained variance {ev:.0%}) "
          f"in {time.time() - t0:.0f}s -> {OUT}")


if __name__ == "__main__":
    main()
