import re

from groq import Groq
from rank_bm25 import BM25Okapi

from app.config import GROQ_API_KEY, GROQ_MODEL
from app.storage.memory_store import get_latest_search


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9]+", (text or "").lower())


def _chunk_text(text: str, chunk_size: int = 180, overlap: int = 35) -> list[str]:
    words = (text or "").split()
    if not words:
        return []

    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end]).strip()
        if chunk:
            chunks.append(chunk)
        if end == len(words):
            break
        start = end - overlap
    return chunks


def answer_from_papers(question: str) -> dict:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is missing. Add it to your .env file.")

    latest = get_latest_search()
    if not latest or not latest.get("papers"):
        raise ValueError("Search for papers first. The current session has no selected papers.")

    chunks = []
    for paper in latest["papers"][:5]:
        source_text = paper.get("full_text") or paper.get("abstract") or ""
        for chunk in _chunk_text(source_text):
            chunks.append({
                "paper_id": paper["paper_id"],
                "title": paper["title"],
                "url": paper["url"],
                "text": chunk,
            })

    if not chunks:
        raise ValueError("No readable paper text is available for RAG.")

    corpus = [_tokens(item["text"]) for item in chunks]
    query_tokens = _tokens(question)
    if not query_tokens:
        raise ValueError("Enter a question with at least 3 meaningful words.")

    bm25 = BM25Okapi(corpus)
    scores = bm25.get_scores(query_tokens)
    top_indices = sorted(range(len(scores)), key=lambda idx: scores[idx], reverse=True)[:6]
    selected = [chunks[idx] for idx in top_indices if scores[idx] > 0]

    if not selected:
        raise ValueError(
            "I could not find matching passages in the available paper text. "
            "The source pages may only provide short snippets or abstracts."
        )

    context_blocks = []
    sources = []
    seen_sources = set()

    for index, item in enumerate(selected, start=1):
        context_blocks.append(
            f"[S{index}] Paper: {item['title']}\n"
            f"URL: {item['url']}\n"
            f"Passage: {item['text']}"
        )
        if item["paper_id"] not in seen_sources:
            sources.append({
                "paper_id": item["paper_id"],
                "title": item["title"],
                "url": item["url"],
            })
            seen_sources.add(item["paper_id"])

    client = Groq(api_key=GROQ_API_KEY)
    completion = client.chat.completions.create(
        model=GROQ_MODEL,
        temperature=0.2,
        max_tokens=1000,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a careful research assistant. Answer only from the supplied "
                    "passages. Cite claims using [S1], [S2], etc. If the passages do not "
                    "contain enough evidence, say what is missing. Never invent findings, "
                    "authors, statistics, or citations. Distinguish evidence from inference."
                ),
            },
            {
                "role": "user",
                "content": f"Question: {question}\n\nRetrieved passages:\n\n"
                           + "\n\n".join(context_blocks),
            },
        ],
    )

    answer = completion.choices[0].message.content or ""
    return {
        "answer": answer.strip(),
        "model": GROQ_MODEL,
        "sources": sources,
        "retrieved_passages": len(selected),
        "content_note": (
            "Answers use the text Tavily could extract from the source pages. "
            "A source may provide only an abstract or partial text."
        ),
    }
