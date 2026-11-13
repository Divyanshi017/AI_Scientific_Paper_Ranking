import json

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.tavily_search import search_papers, fetch_warnings
from app.services.paper_ranking import rank_papers, select_top_papers
from app.services.rag import answer_from_papers, prepare_answer, stream_answer_events
from app.storage import memory_store


class SearchRequest(BaseModel):
    question: str = Field(min_length=5, max_length=500)


class ChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


def public_paper(paper: dict) -> dict:
    return {key: value for key, value in paper.items() if key != "full_text"}


def _session_id(request: Request) -> str:
    return request.headers.get("x-session-id") or memory_store.new_session_id()


def register_api_routes(server: FastAPI) -> None:
    @server.get("/api/health")
    def health():
        return {"status": "ok", "storage": "in-memory"}

    @server.post("/api/search")
    def search(request: SearchRequest, raw: Request):
        try:
            session_id = _session_id(raw)
            papers = search_papers(request.question)
            ranked = rank_papers(request.question, papers)
            # MMR-diverse top 5: accurate relevance, minimal redundancy.
            top_5 = select_top_papers(ranked, k=5)
            top_ids = {paper["paper_id"] for paper in top_5}
            stored = top_5 + [paper for paper in ranked if paper["paper_id"] not in top_ids]
            history_item = memory_store.save_search(request.question, stored, session_id=session_id)
            return {
                "search": history_item,
                "session_id": session_id,
                "fetch_warnings": fetch_warnings(),
                "total_retrieved": len(ranked),
                "top_5": [public_paper(paper) for paper in top_5],
                "all_papers": [public_paper(paper) for paper in ranked],
            }
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error))
        except RuntimeError as error:
            raise HTTPException(status_code=502, detail=str(error))
        except Exception as error:
            raise HTTPException(status_code=502, detail=f"Search failed: {error}")

    @server.get("/api/history")
    def history(request: Request):
        return memory_store.get_search_history(_session_id(request))

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
    def chat(request: ChatRequest, raw: Request):
        try:
            session_id = _session_id(raw)
            return answer_from_papers(request.question, session_id=session_id)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error))
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error))
        except Exception as error:
            raise HTTPException(status_code=502, detail=f"RAG request failed: {error}")

    @server.post("/api/chat/stream")
    def chat_stream(request: ChatRequest, raw: Request):
        """Stream the answer as newline-delimited JSON events (meta, status, delta, done | error)."""
        try:
            ctx = prepare_answer(request.question, session_id=_session_id(raw))
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error))
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error))

        def lines():
            for event in stream_answer_events(ctx):
                yield json.dumps(event, ensure_ascii=False) + "\n"

        return StreamingResponse(
            lines(),
            media_type="application/x-ndjson",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )