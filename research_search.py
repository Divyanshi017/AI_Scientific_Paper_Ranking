"""
research_search.py - enter a research question, fetch papers (Tavily + OpenAlex),
embed them (sentence-transformer), rank, and show the diverse top 5 and all results.

Usage:
    py -3.14 research_search.py
"""
from app.services.tavily_search import search_papers
from app.services.paper_ranking import rank_papers, select_top_papers


def _print_paper(prefix: str, paper: dict) -> None:
    year = paper.get("year") or "n/a"
    source = paper.get("source", "?")
    print(f"{prefix}. {paper['title']} ({year}) [{source}]")
    print(f"   score={paper['ranking_score']:.4f}  embedding={paper['embedding_score']:.4f}  bm25={paper['bm25_score']:.4f}  tavily={paper['tavily_score']:.4f}")
    print(f"   {paper.get('url', '')}")


def main() -> None:
    question = " ".join(input("Enter your research question: ").split())
    if len(question) < 5:
        print("Please enter at least 5 characters.")
        return

    papers = search_papers(question)
    print(f"\nRetrieved {len(papers)} unique papers for: {question}")

    ranked = rank_papers(question, papers)
    top_5 = select_top_papers(ranked, k=5)

    print("\n=== Top 5 papers (diverse selection) ===")
    for i, paper in enumerate(top_5, start=1):
        _print_paper(str(i), paper)
        print()

    print(f"=== All {len(ranked)} ranked papers ===")
    for paper in ranked:
        _print_paper(str(paper["rank"]).rjust(2), paper)


if __name__ == "__main__":
    main()