"""
api/answer.py — Vercel serverless endpoint.
POST {"question": "...", "papers": [...]} -> Groq-hosted RAG answer with [1] [2] citations.

Needs GROQ_API_KEY set in the Vercel project environment (free key from console.groq.com).
Local debug:  python api/answer.py  then POST to http://localhost:8001/api/answer
"""

import os
import re

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
TIMEOUT = 60


@app.after_request
def add_cors(response):
    response.headers.update(CORS_HEADERS)
    return response


@app.route("/api/answer", methods=["POST", "OPTIONS"])
def answer_question():
    if request.method == "OPTIONS":
        return ("", 204)

    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        return jsonify({"error": "GROQ_API_KEY is not set. Add it in Vercel > Settings > Environment Variables (free key: console.groq.com)."}), 503

    data = request.get_json(silent=True) or {}
    question = " ".join(str(data.get("question", "")).split())
    papers = data.get("papers") if isinstance(data.get("papers"), list) else []
    if len(question) < 3:
        return jsonify({"error": "Please enter a research question with at least 3 characters."}), 400
    if not papers:
        return jsonify({"error": "No papers were provided to read."}), 400

    blocks, clean = [], []
    for index, paper in enumerate(papers[:8]):
        title = str((paper or {}).get("title") or "").strip()
        if not title:
            continue
        abstract = str((paper or {}).get("abstract") or "").strip()[:700]
        year = paper.get("year") or "year unknown"
        citations = int(paper.get("citations") or 0)
        blocks.append(f"[{index + 1}] {title} ({year}). Cited by {citations}. Abstract: {abstract or 'n/a'}")
        clean.append(title)
    if not clean:
        return jsonify({"error": "The provided papers had no usable content."}), 400

    response = requests.post(
        GROQ_ENDPOINT,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": MODEL,
            "temperature": 0.2,
            "max_tokens": 600,
            "messages": [
                {"role": "system", "content": "You are a careful research assistant. Answer using ONLY the numbered papers. If they do not contain the answer, say so. Cite [1], [2] etc. Keep it under 250 words."},
                {"role": "user", "content": f"Question: {question}\n\nPapers:\n" + "\n\n".join(blocks)},
            ],
        },
        timeout=TIMEOUT,
    )
    if response.status_code != 200:
        return jsonify({"error": f"Groq error (HTTP {response.status_code}): {response.text[:300]}"}), 502

    try:
        answer = response.json()["choices"][0]["message"]["content"].strip()
    except (ValueError, KeyError, IndexError):
        return jsonify({"error": "Groq returned an unreadable response."}), 502

    used = sorted({int(m) for m in re.findall(r"\[(\d+)\]", answer) if 1 <= int(m) <= len(clean)})
    return jsonify({"answer": answer, "model": MODEL, "used_citations": used})


if __name__ == "__main__":
    app.run(port=8001, debug=False)
