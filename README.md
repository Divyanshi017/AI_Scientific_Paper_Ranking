# Research Paper Assistant

A Python-only frontend built with Plotly Dash, a FastAPI backend, Tavily paper discovery, transparent BM25/Tavily ranking, Groq-powered retrieval-augmented question answering, and temporary in-memory analytics.

## Features

- Search the web for academic-paper candidates using Tavily.
- Collect results from multiple targeted queries and deduplicate URLs.
- Extract available title, author, year, abstract/snippet, source URL and page text.
- Rank results using BM25 text relevance combined with Tavily's relevance score.
- Display the top five papers and the full retrieved candidate list.
- Answer questions using retrieved chunks from the top five papers.
- Track paper-link opens and display overall popularity analytics.
- Keep search history and analytics in Python memory only.

## Important limitations

1. Tavily is a web discovery service, not a guaranteed scholarly index. Results are academic-paper candidates and should be checked at the source.
2. Tavily may only extract an abstract, snippet or partial page. The RAG assistant uses the text actually available; it does not claim to have read a full PDF when it could not retrieve one.
3. Ranking uses BM25 plus Tavily's score. It does not train Random Forest and does not currently use neural embeddings or a Cross-Encoder. This keeps the first Vercel deployment lightweight and avoids pretending a lexical score is semantic understanding.
4. All data is in process memory. It disappears on restart. On Vercel, separate serverless instances may have separate memory, so analytics and history are not reliable persistent cross-user statistics. Use this version as a prototype only.

## Project structure

```text
app/
  main.py
  config.py
  api/routes.py
  frontend/layout.py
  frontend/components.py
  frontend/callbacks.py
  services/tavily_search.py
  services/paper_ranking.py
  services/rag.py
  storage/memory_store.py
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

Open http://127.0.0.1:8000

FastAPI documentation is at http://127.0.0.1:8000/docs

## Deploy to Vercel

1. Push this project to a GitHub repository.
2. Import that repository into Vercel.
3. Add `TAVILY_API_KEY` and `GROQ_API_KEY` under Project Settings → Environment Variables.
4. Deploy. Vercel's Python runtime detects the FastAPI ASGI app exported as `app` from `app/main.py`.
5. Test `/api/health`, `/docs`, the Dash interface, search and RAG.

Do not commit `.env`.

## API endpoints

- `GET /api/health`
- `POST /api/search` with `{"question": "..."}`
- `GET /api/history`
- `GET /api/analytics`
- `POST /api/papers/{paper_id}/view`
- `POST /api/chat` with `{"question": "..."}`

## Ranking explanation

The current score is:

`0.60 * normalized_BM25 + 0.40 * Tavily_score`

BM25 measures query-term relevance across title, abstract/snippet and the first part of extracted page text. Tavily's score is the search provider's relevance score. This is a transparent baseline, not a learned quality score. Citation count, abstract length and open-access status are not used to decide relevance.

## Dashboard interpretation

A paper view is counted when its source link is clicked from the app. It is not proof that the external paper page fully loaded or that the visitor read the paper. The dashboard labels this as views/link opens, not verified reading time.
