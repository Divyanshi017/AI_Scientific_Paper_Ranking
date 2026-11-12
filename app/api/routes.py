from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.services.tavily_search import search_papers
from app.services.paper_ranking import rank_papers
from app.services.rag import answer_from_papers
from app.storage import memory_store


class SearchRequest(BaseModel):
    question: str = Field(min_length=5, max_length=500)


class ChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


def public_paper(paper: dict) -> dict:
    return {key: value for key, value in paper.items() if key != "full_text"}


def register_api_routes(server: FastAPI) -> None:
    @server.get("/api/health")
    def health():
        return {"status": "ok", "storage": "in-memory"}

    @server.post("/api/search")
    def search(request: SearchRequest):
        try:
            papers = search_papers(request.question)
            ranked = rank_papers(request.question, papers)
            history_item = memory_store.save_search(request.question, ranked)
            return {
                "search": history_item,
                "total_retrieved": len(ranked),
                "top_5": [public_paper(paper) for paper in ranked[:5]],
                "all_papers": [public_paper(paper) for paper in ranked],
            }
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error))
        except RuntimeError as error:
            raise HTTPException(status_code=502, detail=str(error))
        except Exception as error:
            raise HTTPException(status_code=502, detail=f"Search failed: {error}")

    @server.get("/api/history")
    def history():
        return memory_store.get_search_history()

    @server.get("/api/analytics")
    def analytics():
        return memory_store.analytics_summary()

    @server.post("/api/papers/{paper_id}/view")
    def paper_view(paper_id: str):
        try:
            return memory_store.record_view(paper_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error))

    @server.post("/api/chat")
    def chat(request: ChatRequest):
        try:
            return answer_from_papers(request.question)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error))
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error))
        except Exception as error:
            raise HTTPException(status_code=502, detail=f"RAG request failed: {error}")
