import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha1
from urllib.parse import urlparse, urlunparse

from tavily import TavilyClient

from app.config import MAX_PAPERS, TAVILY_API_KEY, TAVILY_RESULTS_PER_QUERY


# Hosts that publish actual scholarly papers (journal, conference, preprint servers).
SCHOLARLY_HOSTS = (
    "arxiv.org", "openreview.net", "aclanthology.org", "ieeexplore.ieee.org",
    "dl.acm.org", "link.springer.com", "nature.com", "science.org",
    "sciencedirect.com", "journals.plos.org", "pubmed.ncbi.nlm.nih.gov",
    "biorxiv.org", "medrxiv.org", "papers.ssrn.com", "ssrn.com",
    "doi.org", "researchgate.net", "onlinelibrary.wiley.com", "pnas.org",
    "journals.aps.org", "tandfonline.com", "academic.oup.com", "jstor.org",
    "springer.com", "ncbi.nlm.nih.gov",
)

# Hosts that are almost never the canonical version of a research paper.
BLOCKED_HOSTS = (
    "linkedin.com", "medium.com", "substack.com", "x.com", "twitter.com",
    "facebook.com", "wordpress.com", "blogspot.com", "tumblr.com", "dev.to",
    "reddit.com", "youtube.com",
)

DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b", re.I)
SCHOLARLY_CONTEXT = re.compile(r"journal|proceeding|conference|preprint|volume|issue|published|doi", re.I)

ACADEMIC_DOMAINS = SCHOLARLY_HOSTS  # kept for backward compatibility
_last_warnings: list[str] = []


def fetch_warnings() -> list[str]:
    """Human-readable notes from the last search (currently none are produced)."""
    return list(_last_warnings)


def _clean_url(url: str) -> str:
    parsed = urlparse(url.strip())
    return urlunparse((parsed.scheme, parsed.netloc.lower(), parsed.path.rstrip("/"), "", "", ""))


def _host_matches(host: str, domain: str) -> bool:
    host = host[4:] if host.startswith("www.") else host
    domain = domain[4:] if domain.startswith("www.") else domain
    return host == domain or host.endswith("." + domain)


def _is_academic_candidate(url: str, title: str, content: str) -> bool:
    host = urlparse(url).netloc.lower()
    if any(blocked in host for blocked in BLOCKED_HOSTS):
        return False
    if any(_host_matches(host, scholarly) for scholarly in SCHOLARLY_HOSTS):
        return True
    text = f"{title} {content[:3000]}"
    # A DOI only counts as a scholarly signal when the page also looks like a paper context.
    return bool(DOI_PATTERN.search(text) and SCHOLARLY_CONTEXT.search(text))


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


def _title_stem(title: str) -> str:
    # Drop site/publisher suffixes so the same paper on different hosts matches.
    head = title.split("|")[0]
    head = re.split(r"\s+[-–—]\s+", head)[0]
    return head.strip()


def _norm_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _title_stem(title).lower())


def _dedupe_by_title(papers: list[dict]) -> list[dict]:
    best = {}
    for paper in papers:
        key = _norm_title(paper.get("title", "")) or paper.get("paper_id") or sha1(str(paper).encode()).hexdigest()
        current = best.get(key)
        if current is None or (paper.get("tavily_score", 0.0), len(paper.get("full_text", ""))) > (current.get("tavily_score", 0.0), len(current.get("full_text", ""))):
            best[key] = paper
    return list(best.values())


def search_papers(question: str) -> list[dict]:
    if not TAVILY_API_KEY:
        raise RuntimeError("TAVILY_API_KEY is missing. Add it to your .env file.")

    question = " ".join(question.split())
    if len(question) < 5:
        raise ValueError("Enter a research question with at least 5 characters.")

    _last_warnings.clear()

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
            "academic_check": "Scholarly host/DOI match - verify publisher/source",
            "source": "tavily",
        }

    papers = _dedupe_by_title(list(unique.values()))

    if not papers:
        raise RuntimeError(
            "No identifiable academic-paper candidates found via Tavily. "
            "Try a more specific question or include a research topic and method."
        )

    papers.sort(key=lambda paper: paper["tavily_score"], reverse=True)
    return papers[:MAX_PAPERS]