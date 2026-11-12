import re
from rank_bm25 import BM25Okapi


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9]+", (text or "").lower())


def rank_papers(question: str, papers: list[dict]) -> list[dict]:
    """
    Rank without training a model.

    Tavily's relevance score is combined with BM25 query-to-paper text relevance.
    This is transparent lexical ranking, not a semantic embedding model.
    """
    if not papers:
        return []

    documents = []
    for paper in papers:
        text = " ".join([
            paper.get("title", ""),
            paper.get("abstract", ""),
            paper.get("full_text", "")[:5000],
        ])
        documents.append(tokenize(text))

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

    for index, paper in enumerate(papers):
        tavily_score = max(0.0, min(1.0, float(paper.get("tavily_score", 0.0))))
        bm25_score = normalized_bm25[index]
        final_score = (0.60 * bm25_score) + (0.40 * tavily_score)

        paper["bm25_score"] = round(bm25_score, 4)
        paper["ranking_score"] = round(final_score, 4)
        paper["rank"] = 0
        paper["ranking_explanation"] = (
            "Combined keyword relevance (BM25) and Tavily's search relevance score."
        )

    ranked = sorted(
        papers,
        key=lambda paper: (paper["ranking_score"], paper["tavily_score"]),
        reverse=True,
    )

    for index, paper in enumerate(ranked, start=1):
        paper["rank"] = index

    return ranked
