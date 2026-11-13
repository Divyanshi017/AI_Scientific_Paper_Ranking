import re
from collections.abc import Iterator

from groq import Groq
from rank_bm25 import BM25Okapi

from app.config import GROQ_API_KEY, GROQ_MODEL
from app.storage.memory_store import get_latest_search


ABSTAIN = "The provided papers do not contain enough information to answer this."

# ASD-STE100 Simplified Technical English: the main writing rules, condensed for the model.
STE_RULES = (
    "Write the answer in ASD-STE100 Simplified Technical English (STE):\n"
    "- Use simple, common words. Use each word with one meaning only.\n"
    "- Write one idea in each sentence. Keep descriptive sentences to 25 words or fewer, "
    "and instructions to 20 words or fewer.\n"
    "- Start an instruction with a verb (for example, \"Use a larger corpus.\").\n"
    "- Use the active voice. Use only the simple present, simple past and simple future tenses.\n"
    "- Do not use the -ing form of a verb as a noun or adjective. Do not use phrasal verbs, idioms or slang.\n"
    "- Use articles (the, a, an) and do not leave out words.\n"
    "- Use the same term for the same thing every time.\n"
    "- Keep each paragraph to 6 sentences or fewer. Use a bullet list for 3 or more related items.\n"
    "- Keep technical names (models, methods, datasets, units, numbers) exactly as the passages write them."
)

DRAFT_SYSTEM = (
    "You are a careful research assistant. Answer ONLY from the supplied passages; "
    "use no outside knowledge. Every factual sentence must carry a citation like [S1] "
    "or [S1, S2]. Distinguish evidence (cited) from inference (flag it as inference). "
    "Never invent findings, authors, statistics, or citations. "
    "Write short paragraphs or simple bullet points: no tables, no headings. "
    "Use square brackets for citations, e.g. [S1]. "
    f"If the passages cannot support the answer, reply exactly: \"{ABSTAIN}\"\n\n{STE_RULES}"
)

VERIFY_SYSTEM = (
    "You are a strict fact-checker and STE editor. Compare the ANSWER against the PASSAGES, claim by claim. "
    "Every factual claim must be directly supported by a cited passage. Remove or rewrite any "
    "unsupported claim. You may not add new information. "
    f"If the passages cannot support the question at all, reply exactly: \"{ABSTAIN}\". "
    "Keep the plain-prose format (no tables, no headings) and [S#] citations. "
    "Rewrite any sentence that breaks the STE rules below. "
    f"Return ONLY the corrected answer, nothing else.\n\n{STE_RULES}"
)


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


def _ask_stream(client: Groq, messages: list[dict], temperature: float, max_tokens: int) -> Iterator[str]:
    """Yield answer text pieces as the model produces them (reasoning tokens are skipped)."""
    stream = client.chat.completions.create(
        model=GROQ_MODEL,
        temperature=temperature,
        max_tokens=max_tokens,
        messages=messages,
        stream=True,
    )
    for chunk in stream:
        if not chunk.choices:
            continue
        piece = chunk.choices[0].delta.content
        if piece:
            yield piece


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


def prepare_answer(question: str, session_id: str | None = None) -> dict:
    """Pick the passages for a question. Raises ValueError/RuntimeError before any model call."""
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

    query_tokens = _tokens(question)
    if not query_tokens:
        raise ValueError("Enter a question with at least 3 meaningful words.")

    bm25 = BM25Okapi([_tokens(item["text"]) for item in chunks])
    scores = bm25.get_scores(query_tokens)
    top_indices = sorted(range(len(scores)), key=lambda idx: scores[idx], reverse=True)[:6]
    selected = [chunks[idx] for idx in top_indices if scores[idx] > 0]

    if not selected:
        raise ValueError(
            "I could not find matching passages in the available paper text. "
            "The source pages may only provide short snippets or abstracts."
        )

    sources = []
    seen_sources = set()
    for item in selected:
        if item["paper_id"] not in seen_sources:
            sources.append({"paper_id": item["paper_id"], "title": item["title"], "url": item["url"]})
            seen_sources.add(item["paper_id"])

    return {
        "question": question,
        "selected": selected,
        "context": _passages_block(selected),
        "sources": sources,
        # citations[i] is the paper behind passage [S{i+1}] in the answer.
        "citations": [
            {"paper_id": item["paper_id"], "title": item["title"], "url": item["url"]}
            for item in selected
        ],
    }


def _draft_messages(ctx: dict) -> list[dict]:
    return [
        {"role": "system", "content": DRAFT_SYSTEM},
        {"role": "user", "content": f"Question: {ctx['question']}\n\nRetrieved passages:\n\n{ctx['context']}"},
    ]


def _verify_messages(ctx: dict, draft: str) -> list[dict]:
    return [
        {"role": "system", "content": VERIFY_SYSTEM},
        {
            "role": "user",
            "content": f"Question: {ctx['question']}\n\nPassages:\n\n{ctx['context']}\n\nANSWER:\n{draft}",
        },
    ]


def _result(ctx: dict, draft: str, verified: str) -> dict:
    final = verified or draft
    audit = _audit_citations(final, len(ctx["selected"]))

    content_note = (
        "Two-pass grounding: answers use text Tavily could extract, then a fact-check pass against the same "
        "passages. Answers are written in ASD-STE100 Simplified Technical English. "
        "A source may provide only an abstract or partial text."
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
        "writing_standard": "ASD-STE100",
        "sources": ctx["sources"],
        "citations": ctx["citations"],
        "retrieved_passages": len(ctx["selected"]),
        "verified": audit["verified"],
        "used_citations": audit["used_citations"],
        "invalid_citations": audit["invalid_citations"],
        "abstains": audit["abstains"],
        "content_note": content_note,
    }


def answer_from_papers(question: str, session_id: str | None = None) -> dict:
    ctx = prepare_answer(question, session_id)
    client = _groq_client()
    # Pass 1: strict answer grounded in the passages. Pass 2: fact-check and STE edit.
    draft = _ask(client, _draft_messages(ctx), temperature=0.1, max_tokens=2500)
    verified = _ask(client, _verify_messages(ctx, draft), temperature=0.0, max_tokens=2500)
    return _result(ctx, draft, verified)


def stream_answer_events(ctx: dict) -> Iterator[dict]:
    """Events for a streamed answer: meta, status (drafting/checking), delta text pieces, then done or error.

    Only the fact-checked pass is streamed, so the text the reader sees is the final checked text.
    """
    yield {"type": "meta", "citations": ctx["citations"], "retrieved_passages": len(ctx["selected"])}
    try:
        client = _groq_client()
        yield {"type": "status", "stage": "drafting"}
        draft = _ask(client, _draft_messages(ctx), temperature=0.1, max_tokens=2500)

        yield {"type": "status", "stage": "checking"}
        pieces = []
        for piece in _ask_stream(client, _verify_messages(ctx, draft), temperature=0.0, max_tokens=2500):
            pieces.append(piece)
            yield {"type": "delta", "text": piece}

        yield {"type": "done", **_result(ctx, draft, "".join(pieces).strip())}
    except Exception as error:  # surfaced to the client; the HTTP status is already 200 once streaming starts
        yield {"type": "error", "message": f"RAG request failed: {error}"}
