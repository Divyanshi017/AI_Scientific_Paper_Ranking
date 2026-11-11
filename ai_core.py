"""
ai_core.py — fetch papers from OpenAlex, build features, rank with Random Forest.
Keep it simple: one file, five features, one formula.
"""

import numpy as np
import pandas as pd
import requests
from sklearn.ensemble import RandomForestRegressor
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

OPENALEX_URL = "https://api.openalex.org/works"
CONTACT_EMAIL = "student.project@example.com"
PER_PAGE = 65  # request extra so ~50 remain after de-duplication

FEATURES = ["text_similarity", "citation_score", "recency_score", "abstract_length_score", "open_access_score"]


def reconstruct_abstract(inverted_index):
    """OpenAlex stores abstracts as {word: [positions]}. Put the words back in order."""
    if not isinstance(inverted_index, dict):
        return ""
    words = []
    for word, positions in inverted_index.items():
        if isinstance(positions, int):
            positions = [positions]
        for pos in positions:
            try:
                words.append((int(pos), word))
            except (TypeError, ValueError):
                continue
    words.sort(key=lambda item: item[0])
    return " ".join(word for _, word in words)


def fetch_papers(question, limit=50):
    """Return a DataFrame of ~`limit` unique papers for a research question."""
    question = " ".join(question.split())
    if len(question) < 3:
        raise RuntimeError("Please enter at least 3 characters.")

    params = {"search": question, "per-page": min(PER_PAGE, 100), "mailto": CONTACT_EMAIL}
    headers = {"User-Agent": f"PaperRanking/1.0 (mailto:{CONTACT_EMAIL})"}
    try:
        response = requests.get(OPENALEX_URL, params=params, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.RequestException as error:
        raise RuntimeError(f"OpenAlex could not be reached: {error}") from None

    results = (response.json() or {}).get("results") or []
    papers, seen = [], set()
    for work in results:
        title = (work.get("display_name") or "").strip()
        paper_id = work.get("id")
        key = (paper_id or title.lower()).strip().lower()
        if not title or not key or key in seen:
            continue
        seen.add(key)
        authors = "; ".join(
            (a.get("author") or {}).get("display_name", "") or ""
            for a in (work.get("authorships") or [])
        ).strip(" ;") or "Unknown authors"
        year = work.get("publication_year")
        abstract = work.get("abstract") or reconstruct_abstract(work.get("abstract_inverted_index"))
        papers.append(
            {
                "title": title,
                "authors": authors,
                "abstract": abstract or "",
                "year": int(year) if year else None,
                "citations": int(work.get("cited_by_count") or 0),
                "open_access": bool((work.get("open_access") or {}).get("is_oa")),
                "url": (work.get("primary_location") or {}).get("landing_page_url") or paper_id,
            }
        )
        if len(papers) >= limit:
            break

    if not papers:
        raise RuntimeError("No papers found. Try different wording.")
    return pd.DataFrame(papers)


def _minmax(series):
    """Scale to 0-1 inside this search. If all values are identical, everyone gets 0.5."""
    s = pd.to_numeric(series, errors="coerce")
    if s.notna().sum() == 0:
        return pd.Series(0.5, index=series.index)
    s = s.fillna(s.median())
    lo, hi = s.min(), s.max()
    return pd.Series(0.5, index=series.index) if hi == lo else (s - lo) / (hi - lo)


def add_features(df, question):
    """Add the five model features and the proxy training score."""
    df = df.copy()

    texts = (df["title"].fillna("") + " " + df["abstract"].fillna("")).str.strip()
    try:
        matrix = TfidfVectorizer(stop_words="english", max_features=3000, ngram_range=(1, 2)).fit_transform(list(texts) + [question])
        df["text_similarity"] = cosine_similarity(matrix[:-1], matrix[-1]).ravel().clip(0, 1)
    except ValueError:
        df["text_similarity"] = 0.0

    df["citation_score"] = _minmax(np.log1p(df["citations"].clip(lower=0)))
    df["recency_score"] = _minmax(df["year"].fillna(df["year"].median()) if df["year"].notna().any() else pd.Series(np.nan, index=df.index))
    df["abstract_length"] = df["abstract"].fillna("").str.split().str.len().fillna(0).astype(int)
    df["abstract_length_score"] = _minmax(df["abstract_length"])
    df["open_access_score"] = df["open_access"].astype(float)

    # Weakly supervised training target (a formula, not human labels).
    df["proxy_score"] = (
        0.45 * df["text_similarity"]
        + 0.25 * df["citation_score"]
        + 0.15 * df["recency_score"]
        + 0.10 * df["open_access_score"]
        + 0.05 * df["abstract_length_score"]
        + 0.05 * df["text_similarity"] * df["citation_score"]
    ).clip(0, 1)
    return df


def rank_papers(df):
    """Train the forest on the proxy score, then score and sort every paper."""
    df = df.copy()
    x = df[FEATURES].fillna(0).astype(float)
    model = RandomForestRegressor(n_estimators=100, max_depth=6, random_state=42)
    model.fit(x, df["proxy_score"])
    df["ranking_score"] = model.predict(x).astype(float)
    df = df.sort_values(["ranking_score", "text_similarity", "citations"], ascending=False).reset_index(drop=True)
    df["rank"] = df.index + 1

    importance = pd.Series(model.feature_importances_, index=FEATURES).sort_values(ascending=False)
    return df, importance
