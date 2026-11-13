# Research Paper Assistant (Backend)

A Python-only backend: FastAPI, Tavily paper discovery with an OpenAlex scholarly top-up, transparent ranking (TF-IDF embedding similarity + BM25 + Tavily score), Groq-powered retrieval-augmented question answering, and temporary in-memory analytics. No frontend is included in this version; the pipeline is available through the JSON API and the CLI.

## Features

- Search the web for academic-paper candidates using Tavily.
- If fewer than 50 unique candidates pass the academic filter, top up from OpenAlex (scholarly index).
- Deduplication by URL and normalized title (publisher/host suffixes are ignored) to avoid duplicates.
- Extract available title, author, year, abstract/snippet, source URL and page text.
- Rank using TF-IDF embedding similarity (cosine) combined with BM25 and Tavily's score:
  `0.40 * embedding + 0.35 * BM25 + 0.25 * Tavily_score`
- Return the top five papers and the full ranked list of 50.
- Answer questions using retrieved chunks from the top papers (RAG).
- Track paper-link opens and display overall popularity analytics.
- Keep search history and analytics in Python memory only.

## Important limitations

1. Tavily is a web discovery service, not a guaranteed scholarly index. OpenAlex (when used to top up) is a scholarly index, but retrieved records can still be stale or incomplete. Verify everything at the source.
2. Tavily may only extract an abstract, snippet or partial page. The RAG assistant uses the text actually available.
3. Ranking is lexical/vector-free proxy scoring (TF-IDF + BM25 + Tavily score). It does not train a model.
4. All data is in process memory. It disappears on restart. On Vercel, separate serverless instances may have separate memory, so analytics and history are not reliable persistent cross-user statistics.

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