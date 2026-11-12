import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha1
from urllib.parse import urlparse, urlunparse

from tavily import TavilyClient

from app.config import MAX_PAPERS, TAVILY_API_KEY, TAVILY_RESULTS_PER_QUERY


ACADEMIC_DOMAINS = (
    "arxiv.org", "openreview.net", "aclanthology.org", "ieeexplore.ieee.org",
    "dl.acm.org", "link.springer.com", "nature.com", "sciencedirect.com",
    "journals.plos.org", "pubmed.ncbi.nlm.nih.gov", "biorxiv.org",
    "medrxiv.org", "papers.ssrn.com", "doi.org", "researchgate.net",
)

ACADEMIC_TERMS = (
    "abstract", "methodology", "method", "results", "conclusion",
    "preprint", "journal", "conference", "doi", "research paper",
    "proceedings", "arxiv",
)


def _clean_url(url: str) -> str:
    parsed = urlparse(url.strip())
    return urlunparse((parsed.scheme, parsed.netloc.lower(), parsed.path.rstrip("/"), "", "", ""))


def _is_academic_candidate(url: str, title: str, content: str) -> bool:
    host = urlparse(url).netloc.lower()
    text = f"{title} {content[:2500]}".lower()
    return (
        any(domain in host for domain in ACADEMIC_DOMAINS)
        or any(term in text for term in ACADEMIC_TERMS)
        or bool(re.search(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", text, re.I))
    )


def _extract_year(text: str):
    match = re.search(r"\b(19[5-9]\d|20[0-2]\d)\b", text)
    return int(match.group(1)) if match else None


def _extract_authors(text: str) -> str:
    patterns = [
        r"(?im)^\s*authors?\s*:\s*(.{5,220})$",
        r"(?im)^\s*by\s+([A-Z][A-Za-z.,' -]{5,150})$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text[:5000])
        if match:
            return re.sub(r"\s+", " ", match.group(1)).strip()
    return "Not identified by Tavily"


def _queries(question: str) -> list[str]:
    return [
        f"{question} research paper abstract",
        f"{question} academic study journal conference paper",
        f"{question} site:arxiv.org OR site:openreview.net",
    ]


def search_papers(question: str) -> list[dict]:
    if not TAVILY_API_KEY:
        raise RuntimeError("TAVILY_API_KEY is missing. Add it to your .env file.")

    question = " ".join(question.split())
    if len(question) < 5:
        raise ValueError("Enter a research question with at least 5 characters.")

    client = TavilyClient(api_key=TAVILY_API_KEY)
    query_list = _queries(question)
    results = []

    # Run three Tavily searches concurrently to collect a wider candidate pool.
    with ThreadPoolExecutor(max_workers=len(query_list)) as pool:
        futures = [
            pool.submit(
                client.search,
                query,
                search_depth="advanced",
                topic="general",
                max_results=TAVILY_RESULTS_PER_QUERY,
                include_raw_content="markdown",
                include_answer=False,
            )
            for query in query_list
        ]
        for future in as_completed(futures):
            response = future.result()
            results.extend(response.get("results", []))

    unique = {}
    for item in results:
        url = (item.get("url") or "").strip()
        title = (item.get("title") or "").strip()
        if not url or not title:
            continue

        clean_url = _clean_url(url)
        if not clean_url:
            continue

        raw_content = (item.get("raw_content") or "").strip()
        snippet = (item.get("content") or "").strip()
        combined = raw_content or snippet

        if not _is_academic_candidate(url, title, combined):
            continue

        paper_id = sha1(clean_url.encode("utf-8")).hexdigest()[:16]
        if paper_id in unique:
            # Keep the version with the most usable text.
            if len(combined) > len(unique[paper_id]["full_text"]):
                unique[paper_id]["full_text"] = combined
            continue

        unique[paper_id] = {
            "paper_id": paper_id,
            "title": title,
            "authors": _extract_authors(combined),
            "year": _extract_year(f"{title} {combined[:3000]}"),
            "abstract": snippet[:3500],
            "full_text": combined[:30000],
            "url": url,
            "domain": urlparse(url).netloc.replace("www.", ""),
            "tavily_score": float(item.get("score") or 0.0),
            "views": 0,
            "academic_check": "Candidate — verify publisher/source",
        }

    papers = list(unique.values())
    if not papers:
        raise RuntimeError(
            "Tavily did not return identifiable academic-paper candidates. "
            "Try a more specific question or include a research topic and method."
        )

    papers.sort(key=lambda paper: paper["tavily_score"], reverse=True)
    return papers[:MAX_PAPERS]
