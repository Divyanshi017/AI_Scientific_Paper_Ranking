# AI Scientific Paper Ranking

Ask a research question → ~50 papers are fetched from OpenAlex, ranked by a **Random Forest**, and a Groq-hosted LLM **answers your question** from the top papers with citations. Static frontend + Python serverless functions — deployable on **Vercel** for free.

## Structure

```
ai_core.py        fetch + features + Random Forest ranking (used by api/rank.py)
api/rank.py       POST /api/rank  → 50 ranked papers as JSON
api/answer.py     POST /api/answer → Groq RAG answer with [1][2] citations (needs GROQ_API_KEY)
index.html        the whole UI (hero, search, RAG answer, metrics, top 5, 5 charts, CSV)
style.css         styling (teal gradient hero, cream background, coral accents)
app.js            frontend logic (fetch, render, Plotly charts, CSV download)
vercel.json       function config
```

No build step. No frameworks. One `GROQ_API_KEY` env var.

## Run locally

**One command:**
```powershell
python dev_server.py     # website + API on http://localhost:8000 (opens the browser for you)
```
Open http://localhost:8000. That's it — one terminal.

Or run `vercel dev` (Vercel CLI) for the exact production setup.

## Deploy on Vercel (free)

1. Push this folder to GitHub (check that `.env` is not committed).
2. https://vercel.com → **Add New → Project** → import the repo. Framework preset: **Other**. Leave everything default.
3. Add environment variable **`GROQ_API_KEY`** = your free key from https://console.groq.com (Settings → Environment Variables).
4. Deploy → open the URL → search → click **Generate answer**.

The frontend calls the same-origin `/api/*` routes; no extra config needed on Vercel.

## How it works

1. OpenAlex (~50 papers, de-duplicated) → TF-IDF similarity + citation/recency/length/open-access features → `RandomForestRegressor` trained on a proxy formula → ranking scores → top 5.
2. Weak supervision by formula — **not** human-labelled relevance. Weakly supervised, not verified usefulness.
3. The AI answer (RAG) inserts the top papers into a prompt; Groq's `llama-3.1-8b-instant` answers with citations.

## Limitations

Proxy-trained scores; TF-IDF misses synonymy; citations favour older work; open access ≠ quality; ~50 papers is one search sample; the LLM can misread abstracts — verify against the cited papers.
