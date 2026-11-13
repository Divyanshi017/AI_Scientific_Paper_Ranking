import re

from groq import Groq
from rank_bm25 import BM25Okapi

from app.config import GROQ_API_KEY, GROQ_MODEL
from app.storage.memory_store import get_latest_search


ABSTAIN = "The provided papers do not contain enough information to answer this."


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


def _groq_client() -> Groq:
    return Groq(api_key=GROQ_API_KEY)


def _ask(client: Groq, messages: list[dict], temperature: float, max_tokens: int) -> str:
    completion = client.chat.completions.create(
        model=GROQ_MODEL,
        temperature=temperature,
        max_tokens=max_tokens,
        messages=messages,
    )
    return (completion.choices[0].message.content or "").strip()


def _passages_block(selected: list[dict]) -> str:
    blocks = []
    for index, item in enumerate(selected, start=1):
        blocks.append(
            f"[S{index}] Paper: {item['title']}\n"
            f"URL: {item['url']}\n"
            f"Passage: {item['text']}"
        )
    return "\n\n".join(blocks)


def _audit_citations(answer: str, max_sources: int) -> dict:
    """Inspect [S#] markers in the answer. Returns used/invalid lists and a verified flag."""
    used = sorted({int(marker) for marker in re.findall(r"S(\d+)", answer or "")})
    valid = [n for n in used if 1 <= n <= max_sources]
    invalid = [n for n in used if n not in valid]
    abstains = (answer or "").strip().upper() == ABSTAIN.upper()
    verified = abstains or (len(valid) > 0 and len(invalid) == 0)
    return {
        "verified": verified,
        "used_citations": valid,
        "invalid_citations": invalid,
        "abstains": abstains,
    }


def answer_from_papers(question: str, session_id: str | None = None) -> dict:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is missing. Add it to your .env file.")

    latest = get_latest_search(session_id)
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

    context_blocks = _passages_block(selected)
    sources = []
    seen_sources = set()
    for item in selected:
        if item["paper_id"] not in seen_sources:
            sources.append({
                "paper_id": item["paper_id"],
                "title": item["title"],
                "url": item["url"],
            })
            seen_sources.add(item["paper_id"])

    client = _groq_client()

    # Pass 1: strict single-pass answer grounded in the passages.
    draft = _ask(
        client,
        [
            {
                "role": "system",
                "content": (
                    "You are a careful research assistant. Answer ONLY from the supplied passages; "
                    "use no outside knowledge. Every factual sentence must carry a citation like [S1] "
                    "or [S1, S2]. Distinguish evidence (cited) from inference (flag it as inference). "
                    "Never invent findings, authors, statistics, or citations. "
                    f"If the passages cannot support the answer, reply exactly: \"{ABSTAIN}\""
                ),
            },
            {
                "role": "user",
                "content": f"Question: {question}\n\nRetrieved passages:\n\n{context_blocks}",
            },
        ],
        temperature=0.1,
        max_tokens=1000,
    )

    # Pass 2: fact-check the draft against the same passages and strip anything unsupported.
    verified = _ask(
        client,
        [
            {
                "role": "system",
                "content": (
                    "You are a strict fact-checker. Compare the ANSWER against the PASSAGES, claim by claim. "
                    "Every factual claim must be directly supported by a cited passage. Remove or rewrite any "
                    "unsupported claim. You may not add new information. "
                    f"If the passages cannot support the question at all, reply exactly: \"{ABSTAIN}\". "
                    "Return ONLY the corrected answer, nothing else."
                ),
            },
            {
                "role": "user",
                "content": f"Question: {question}\n\nPassages:\n\n{context_blocks}\n\nANSWER:\n{draft}",
            },
        ],
        temperature=0.0,
        max_tokens=1000,
    )

    final = verified or draft
    audit = _audit_citations(final, len(selected))

    content_note = (
        "Two-pass grounding: answers use text Tavily could extract, then a fact-check pass against the same "
        "passages. A source may provide only an abstract or partial text."
    )
    if not audit["verified"] and not audit["abstains"]:
        content_note += (
            " The final answer lacks explicit valid citations or references sources that were not retrieved; "
            "treat its claims with caution."
        )

    return {
        "answer": final,
        "draft_answer": draft if verified != draft else None,
        "model": GROQ_MODEL,
        "sources": sources,
        "retrieved_passages": len(selected),
        "verified": audit["verified"],
        "used_citations": audit["used_citations"],
        "invalid_citations": audit["invalid_citations"],
        "abstains": audit["abstains"],
        "content_note": content_note,
    }