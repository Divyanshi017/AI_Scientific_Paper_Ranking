import math

import numpy as np

from app.services import paper_ranking
from app.services.tavily_search import _is_academic_candidate
from app.services.openalex_search import _reconstruct_abstract
from app.services.rag import _chunk_text, _audit_citations, ABSTAIN


def test_host_match_blocks_spoofed_suffix():
    assert _is_academic_candidate("https://arxiv.org/abs/2501.00001", "t", "x")
    assert not _is_academic_candidate("https://arxiv.org.evil.com/abs/2501.00001", "t", "x")
    assert not _is_academic_candidate("https://fakenature.com/articles/123", "Some journal", "")


def test_blog_domains_rejected_even_with_doi_look():
    assert not _is_academic_candidate("https://medium.com/whatever", "Journals", "doi: 10.1000/xyz")


def test_doi_requires_paper_context():
    assert not _is_academic_candidate("https://example.com/blog/post", "t", "no markers here")
    assert _is_academic_candidate("https://example.com/blog/post", "t", "Published in journal; doi: 10.1038/xyz")


def test_reconstruct_abstract():
    inverted = {"hello": [0], "world": [1], "friend": [2]}
    assert _reconstruct_abstract(inverted) == "hello world friend"


def test_chunk_text_overlap():
    text = " ".join(f"word{i}" for i in range(60))
    chunks = _chunk_text(text, chunk_size=20, overlap=5)
    assert len(chunks) >= 3
    assert "word0" in chunks[0]


def test_audit_citations_flags_missing_or_invalid():
    assert _audit_citations(ABSTAIN, 3)["verified"]
    assert not _audit_citations("LLMs improved accuracy in all studies.", 3)["verified"]
    assert _audit_citations("Accuracy improved [S1].", 3)["verified"]
    result = _audit_citations("Accuracy improved [S9].", 3)
    assert not result["verified"]
    assert result["invalid_citations"] == [9]


def _fake_vectors(texts):
    out = []
    for _ in texts:
        out.append(np.ones(4, dtype=float))
    return np.array(out), False


def _papers(scores):
    papers = []
    for i, score in enumerate(scores):
        papers.append({
            "paper_id": f"p{i}",
            "title": f"paper {i}",
            "abstract": f"abstract {i}",
            "full_text": f"text {i}",
            "tavily_score": 0.5,
            "ranking_score": score,
            "rank": 0,
        })
    return papers


def test_mmr_prefers_diverse_papers(monkeypatch):
    monkeypatch.setattr(paper_ranking, "_vectors", _fake_vectors)
    ranked = _papers([0.9, 0.88, 0.85, 0.8, 0.6, 0.55])
    chosen = paper_ranking.select_top_papers(ranked, k=4)
    assert len(chosen) == 4
    assert ranked[0] in chosen


def test_rank_papers_orders_descending(monkeypatch):
    monkeypatch.setattr(paper_ranking, "_vectors", _fake_vectors)
    papers = [
        {"paper_id": "a", "title": "retrieval augmented generation", "abstract": "rag reduces hallucinations", "full_text": "rag", "tavily_score": 0.8},
        {"paper_id": "b", "title": "marine biology", "abstract": "coral reefs", "full_text": "ocean", "tavily_score": 0.1},
    ]
    ranked = paper_ranking.rank_papers("retrieval augmented generation hallucinations", papers)
    assert ranked[0]["ranking_score"] >= ranked[1]["ranking_score"]
    assert ranked[0]["embedding_score"] is not None