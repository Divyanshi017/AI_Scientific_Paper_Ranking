import os
import re

import numpy as np
from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import normalize

_embedder = None
_embedder_loaded = False
_EMBED_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9]+", (text or "").lower())


def _paper_text(paper: dict) -> str:
    return " ".join([
        paper.get("title", ""),
        paper.get("abstract", ""),
        paper.get("full_text", "")[:5000],
    ]).strip()


def _get_embedder():
    """Load the sentence-transformer lazily. Falls back to TF-IDF if unavailable."""
    global _embedder, _embedder_loaded
    if not _embedder_loaded:
        _embedder_loaded = True
        try:
            from sentence_transformers import SentenceTransformer
            _embedder = SentenceTransformer(_EMBED_MODEL)
        except Exception:
            _embedder = None
    return _embedder


def _vectors(texts: list[str]) -> tuple[np.ndarray, bool]:
    """Return normalized embedding vectors (dense) and whether semantic embeddings were used."""
    try:
        model = _get_embedder()
        if model is not None:
            arr = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
            return arr.astype(float), True
        matrix = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            max_features=3000,
        ).fit_transform(texts)
        return normalize(matrix).toarray().astype(float), False
    except Exception:
        return np.zeros((len(texts), 1), dtype=float), False


def select_top_papers(ranked: list[dict], k: int = 5, lambda_: float = 0.75) -> list[dict]:
    """
    MMR-style selection for the top-k: keeps high ranking_score papers but drops
    near-duplicates, so the chosen papers cover different aspects of the question.
    """
    if len(ranked) <= k:
        return list(ranked)

    docs = [_paper_text(paper) for paper in ranked]
    vectors, _ = _vectors(docs)
    similarities = vectors @ vectors.T

    chosen: list[int] = []
    chosen_set: set[int] = set()

    seed = max(
        range(len(ranked)),
        key=lambda i: (float(ranked[i].get("ranking_score", 0.0)), float(ranked[i].get("tavily_score", 0.0))),
    )
    chosen.append(seed)
    chosen_set.add(seed)

    while len(chosen) < k:
        best_index, best_mmr = None, -10 ** 9
        for i in range(len(ranked)):
            if i in chosen_set:
                continue
            redundancy = float(np.max(similarities[i, chosen])) if chosen else 0.0
            mmr = (
                lambda_ * float(ranked[i].get("ranking_score", 0.0))
                - (1 - lambda_) * redundancy
            )
            if mmr > best_mmr:
                best_mmr, best_index = mmr, i
        chosen.append(best_index)
        chosen_set.add(best_index)

    return [ranked[i] for i in chosen]


def rank_papers(question: str, papers: list[dict]) -> list[dict]:
    """
    Rank papers with semantic embeddings (sentence-transformer when available,
    TF-IDF otherwise), BM25 keyword relevance and Tavily's search score.
    """
    if not papers:
        return []

    documents = []
    docs_text = []
    for paper in papers:
        text = _paper_text(paper)
        documents.append(tokenize(text))
        docs_text.append(text)

    query_tokens = tokenize(question)
    if not query_tokens:
        query_tokens = ["research"]

    bm25 = BM25Okapi(documents)
    raw_scores = [float(value) for value in bm25.get_scores(query_tokens)]

    low, high = min(raw_scores), max(raw_scores)
    if high == low:
        normalized_bm25 = [0.0 for _ in raw_scores]
    else:
        normalized_bm25 = [(value - low) / (high - low) for value in raw_scores]

    vectors, semantic = _vectors(docs_text + [question])
    embedding_scores = [float(np.clip(value, 0.0, 1.0)) for value in (vectors[:-1] @ vectors[-1])]

    if semantic:
        embedding_weight, bm25_weight = 0.50, 0.25
        embedding_note = "semantic embeddings"
    else:
        embedding_weight, bm25_weight = 0.40, 0.35
        embedding_note = "TF-IDF embeddings (sentence transformer unavailable)"
    tavily_weight = 1.0 - embedding_weight - bm25_weight

    for index, paper in enumerate(papers):
        tavily_score = max(0.0, min(1.0, float(paper.get("tavily_score", 0.0))))
        bm25_score = normalized_bm25[index]
        embedding_score = embedding_scores[index]
        final_score = (
            embedding_weight * embedding_score
            + bm25_weight * bm25_score
            + tavily_weight * tavily_score
        )

        paper["embedding_score"] = round(embedding_score, 4)
        paper["bm25_score"] = round(bm25_score, 4)
        paper["ranking_score"] = round(final_score, 4)
        paper["rank"] = 0
        paper["ranking_explanation"] = (
            f"Combined {embedding_note} similarity, keyword relevance (BM25) "
            "and Tavily's search relevance score."
        )

    ranked = sorted(
        papers,
        key=lambda paper: (paper["ranking_score"], paper["tavily_score"]),
        reverse=True,
    )

    for index, paper in enumerate(ranked, start=1):
        paper["rank"] = index

    return ranked