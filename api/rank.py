"""
api/rank.py — Vercel serverless endpoint.
POST {"question": "..."} -> ranked papers as JSON (same logic as the Streamlit app).

Local debug:  python api/rank.py   then POST to http://localhost:8000/api/rank
"""

import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import numpy as np
import pandas as pd
from flask import Flask, jsonify, request

import ai_core

app = Flask(__name__)
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


@app.after_request
def add_cors(response):
    response.headers.update(CORS_HEADERS)
    return response


@app.route("/api/rank", methods=["POST", "OPTIONS"])
def rank_papers():
    if request.method == "OPTIONS":
        return ("", 204)

    question = " ".join(str((request.get_json(silent=True) or {}).get("question", "")).split())
    if len(question) < 3:
        return jsonify({"error": "Please enter a research question with at least 3 characters."}), 400

    try:
        papers = ai_core.fetch_papers(question, limit=50)
        papers = ai_core.add_features(papers, question)
        ranked, importance = ai_core.rank_papers(papers)
    except RuntimeError as error:
        return jsonify({"error": str(error)}), 502
    except Exception as error:
        return jsonify({"error": f"The analysis could not be completed: {error}"}), 500

    rows = []
    for record in ranked.to_dict(orient="records"):
        rows.append({
            "rank": int(record["rank"]),
            "title": str(record["title"]),
            "authors": str(record["authors"]),
            "abstract": record.get("abstract") or "",
            "year": None if pd.isna(record.get("year")) else int(record["year"]),
            "citations": int(record["citations"]),
            "open_access": bool(record["open_access"]),
            "url": record.get("url"),
            "text_similarity": round(float(record["text_similarity"]), 4),
            "citation_score": round(float(record["citation_score"]), 4),
            "recency_score": round(float(record["recency_score"]), 4),
            "abstract_length": int(record["abstract_length"]),
            "abstract_length_score": round(float(record["abstract_length_score"]), 4),
            "open_access_score": float(record["open_access_score"]),
            "proxy_score": round(float(record["proxy_score"]), 4),
            "ranking_score": round(float(record["ranking_score"]), 4),
        })

    labels = {
        "text_similarity": "Textual similarity",
        "citation_score": "Citation score",
        "recency_score": "Publication recency",
        "abstract_length_score": "Abstract length",
        "open_access_score": "Open-access score",
    }
    return jsonify({
        "papers": rows,
        "importance": [{"label": labels.get(k, k), "pct": round(float(v) * 100, 1)} for k, v in importance.items()],
        "n_papers": len(rows),
    })


if __name__ == "__main__":
    app.run(port=8000, debug=False)
