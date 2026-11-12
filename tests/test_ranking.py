from app.services.paper_ranking import rank_papers


def test_ranker_returns_descending_scores():
    papers = [
        {
            "paper_id": "a", "title": "RAG for language models",
            "abstract": "Retrieval augmented generation reduces hallucinations.",
            "full_text": "Retrieval augmented generation and language model evaluation.",
            "tavily_score": 0.8,
        },
        {
            "paper_id": "b", "title": "Marine biology",
            "abstract": "Coral reef ecosystems and ocean biodiversity.",
            "full_text": "Marine biology study.",
            "tavily_score": 0.2,
        },
    ]
    ranked = rank_papers("retrieval augmented generation hallucinations", papers)
    assert len(ranked) == 2
    assert ranked[0]["rank"] == 1
    assert ranked[0]["ranking_score"] >= ranked[1]["ranking_score"]
