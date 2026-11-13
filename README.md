# Research Paper Assistant (Backend)

A Python-only FastAPI backend: Tavily paper discovery (strict scholarly filter) with an OpenAlex top-up, transparent ranking (semantic embeddings + BM25 + Tavily score), diversified top-5 selection for RAG, Groq-powered two-pass question answering, and temporary in-memory analytics. No frontend is included in this version.

## Features

- Search the web for academic-paper candidates using Tavily.
- Strict filter: a candidate passes only if it comes from a scholarly host (journal, conference, preprint server) or contains an explicit DOI. Non-paper hosts (blogs, social media) are rejected; this avoids «abstract»/«methodology» keyword false positives.
- If fewer than 50 unique candidates pass, top up from OpenAlex (scholarly index) so every question returns 50 unique papers.
- Deduplication by URL and normalized title (publisher/host suffixes are ignored).
- Rank using sentence-transformer semantic similarity (cosine) combined with BM25 and Tavily's score:
  `0.50 * semantic_embedding + 0.25 * BM25 + 0.25 * Tavily_score`
  (falls back to TF-IDF embedding similarity if the model cannot load).
- Top-5 selection is MMR-diversified: high-ranked papers are kept, but near-duplicates are dropped so the chosen five cover different aspects of the question.
- RAG answers are two-pass: a strict grounded answer followed by a fact-check that strips unsupported claims. If the passages cannot support the answer, the assistant abstains ("The provided papers do not contain enough information to answer this.").
- Track paper-link opens and display overall popularity analytics.
- Keep search history and analytics in Python memory only.

## Important limitations

1. Tavily is a web discovery service. The scholarly filter is strict but not infallible; retrieved papers still need verification at the source.
2. Extracted full text may be only an abstract or snippet. The RAG assistant uses the text actually available.
3. Semantic ranking is embedding-based relevance, not a guarantee of quality or correctness.
4. The fact-check pass reduces but cannot eliminate hallucinations; verify against the cited papers.
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

Then run:

```powershell
python -m app.main
```

FastAPI documentation is at http://127.0.0.1:8000/docs.

Or run the CLI, which asks for your research question and prints the ranked papers:

```powershell
py -3.12 research_search.py
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
- `POST /api/search` with `{"question": "..."}`
- `GET /api/history`
- `GET /api/analytics`
- `POST /api/papers/{paper_id}/view`
- `POST /api/chat` with `{"question": "..."}`