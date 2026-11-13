# Research Paper Assistant (Backend)

A Python-only FastAPI backend: Tavily paper discovery (strict scholarly filter) with an OpenAlex top-up, transparent ranking (semantic embeddings + BM25 + Tavily score), diversified top-5 selection for RAG, Groq-powered two-pass question answering, and temporary in-memory analytics scoped per API session. No frontend is included in this version.

## Features

- Search the web for academic-paper candidates using Tavily.
- Strict filter: a candidate passes only if its host is a scholarly publisher/conference/preprint server (exact or sub-domain) or it contains an explicit DOI alongside paper-style context (journal/proceedings/preprint/volume/etc.). Blogs and social hosts are rejected to avoid false academic matches.
- If fewer than 50 unique candidates pass, top up from OpenAlex (scholarly index) so every question returns 50 unique papers. Missing/unavailable OpenAlex degrades gracefully and surfaces a `fetch_warnings` note instead of silently returning fewer papers.
- Deduplication by URL and normalized title (publisher/host suffixes are ignored).
- Rank using sentence-transformer semantic similarity (cosine) combined with BM25 and Tavily's score:
  `0.50 * semantic_embedding + 0.25 * BM25 + 0.25 * Tavily_score`
  (falls back to TF-IDF embedding similarity if the model cannot load; ranking still works, just without semantic signal).
- Top-5 selection is MMR-diversified: high-ranked papers are kept, but near-duplicates are dropped so the chosen five cover different aspects of the question.
- RAG answers are two-pass: a strict grounded answer followed by a fact-check that strips unsupported claims. Citation audit: answers contain `verified`, `used_citations` and `invalid_citations` instead of an unconditional "verified" flag.
- If the passages cannot support the answer, the assistant abstains ("The provided papers do not contain enough information to answer this.").
- Track paper-link opens and display overall popularity analytics.
- Search sessions are isolated: `POST /api/search` accepts an optional `X-Session-Id` header; RAG reads only the caller's last search.

## Important limitations

1. Tavily is a web discovery service. The scholarly filter is strict but not infallible; retrieved papers still need verification at the source.
2. Extracted full text may be only an abstract or snippet. The RAG assistant uses the text actually available.
3. Semantic ranking is embedding-based relevance, not a guarantee of quality or correctness.
4. The fact-check pass reduces but cannot eliminate hallucinations; `verified` is only set when the answer carries valid citations (or explicitly abstains).
5. All data is in process memory. It disappears on restart. On Vercel, separate serverless instances may have separate memory, so analytics and history are not reliable persistent cross-user statistics.

## Project structure

```text
app/
  main.py
  config.py
  api/routes.py
  services/tavily_search.py
  services/openalex_search.py
  services/paper_ranking.py
  services/rag.py
  storage/memory_store.py
tests/
  test_ranking.py
  test_backend.py
research_search.py
requirements.txt
.env.example
vercel.json
```

## Run locally (Windows PowerShell)

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Open `.env` and add your actual keys:

- `TAVILY_API_KEY`
- `GROQ_API_KEY`

Optional: `OPENALEX_MAILTO` (OpenAlex politeness contact; defaults to a placeholder).

Then run:

```powershell
python -m app.main
```

FastAPI documentation is at http://127.0.0.1:8000/docs.

Or run the CLI, which asks for your research question and prints the ranked papers:

```powershell
py -3.12 research_search.py
```

Run tests with:

```powershell
python -m pytest tests
```

## Deploy to Vercel

1. Push this project to a GitHub repository.
2. Import that repository into Vercel.
3. Add `TAVILY_API_KEY` and `GROQ_API_KEY` under Project Settings -> Environment Variables.
4. Deploy. Vercel's Python runtime detects the FastAPI ASGI app exported as `app` from `app/main.py`.
5. Test `/api/health`, `/docs`, `/api/search`, `/api/chat`.

Do not commit `.env`.

## API endpoints

- `GET /api/health`
- `POST /api/search` with `{"question": "..."}` — returns `top_5`, `all_papers`, `session_id`, `fetch_warnings`
- `GET /api/history` — scoped to the caller's `X-Session-Id`
- `GET /api/analytics`
- `POST /api/papers/{paper_id}/view`
- `POST /api/chat` with `{"question": "..."}` — answers scoped to the caller's last search for that `X-Session-Id`