from hashlib import sha1
from urllib.parse import urlparse

import requests

from app.config import OPENALEX_MAILTO

OPENALEX_URL = "https://api.openalex.org/works"


def _reconstruct_abstract(inverted_index) -> str:
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


def search_papers_openalex(question: str, limit: int = 50) -> list[dict]:
    question = " ".join(question.split())
    if len(question) < 5:
        raise ValueError("Enter a research question with at least 5 characters.")

    params = {"search": question, "per-page": 65, "mailto": OPENALEX_MAILTO}
    headers = {"User-Agent": f"ResearchPaperAssistant/1.0 (mailto:{OPENALEX_MAILTO})"}

    response = requests.get(OPENALEX_URL, params=params, headers=headers, timeout=30)
    response.raise_for_status()

    results = (response.json() or {}).get("results") or []
    papers = []
    seen = set()

    for work in results:
        try:
            title = (work.get("display_name") or "").strip()
            if not title:
                continue

            doi = (work.get("doi") or "").lower()
            work_id = work.get("id") or ""
            authors = "; ".join(
                (authorship.get("author") or {}).get("display_name", "") or ""
                for authorship in (work.get("authorships") or [])
            ).strip(" ;") or "Unknown authors"
            year = work.get("publication_year")
            abstract = _reconstruct_abstract(work.get("abstract_inverted_index"))
            url = (work.get("primary_location") or {}).get("landing_page_url") or work_id

            paper_id = sha1((doi or work_id or title.lower()).encode("utf-8")).hexdigest()[:16]
            if paper_id in seen:
                continue
            seen.add(paper_id)

            papers.append({
                "paper_id": paper_id,
                "title": title,
                "authors": authors,
                "year": int(year) if year else None,
                "abstract": abstract[:3500],
                "full_text": abstract[:30000],
                "url": url,
                "domain": urlparse(url).netloc.replace("www.", "") if url else "openalex.org",
                "tavily_score": 0.5,
                "views": 0,
                "academic_check": "Scholarly index (OpenAlex) - verify publisher/source",
                "source": "openalex",
            })
        except Exception:
            # One malformed record must not kill the whole top-up.
            continue

        if len(papers) >= limit:
            break

    return papers