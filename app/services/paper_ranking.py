import re

from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9]+", (text or "").lower())


def _paper_text(paper: dict) -> str:
    return " ".join([
        paper.get("title", ""),
        paper.get("abstract", ""),
        paper.get("full_text", "")[:5000],
    ]).strip()


def _embedding_scores(question: str, docs: list[str]) -> list[float]:
    """TF-IDF embeddings of the paper texts vs the question (cosine similarity)."""
    try:
        vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            max_features=3000,
        )
        matrix = vectorizer.fit_transform(docs + [question])
        similarity = cosine_similarity(matrix[:-1], matrix[-1]).ravel().clip(0, 1)
        return [float(value) for value in similarity]
    except ValueError:
        return [0.0 for _ in docs]


def rank_papers(question: str, papers: list[dict]) -> list[dict]:
    """
    Rank papers by combining TF-IDF embedding similarity (semantic relevance),
    BM25 keyword relevance, and Tavily's search score.
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

    embedding_scores = _embedding_scores(question, docs_text)

    for index, paper in enumerate(papers):
        tavily_score = max(0.0, min(1.0, float(paper.get("tavily_score", 0.0))))
        bm25_score = normalized_bm25[index]
        embedding_score = embedding_scores[index]
        final_score = (
            0.40 * embedding_score
            + 0.35 * bm25_score
            + 0.25 * tavily_score
        )

        paper["embedding_score"] = round(embedding_score, 4)
        paper["bm25_score"] = round(bm25_score, 4)
        paper["ranking_score"] = round(final_score, 4)
        paper["rank"] = 0
        paper["ranking_explanation"] = (
            "Combined TF-IDF embedding similarity, keyword relevance (BM25) "
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
