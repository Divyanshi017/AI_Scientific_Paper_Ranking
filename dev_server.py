"""
dev_server.py — local development AND the whole app on one port.
Serves the website (index.html / style.css / app.js) and both API endpoints
on http://localhost:8000 — one command, one terminal.

    pip install -r requirements.txt
    python dev_server.py
    # open http://localhost:8000

Set GROQ_API_KEY for the AI Answer tab:
    set GROQ_API_KEY=gsk_...
"""

import os
import sys
import threading
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from flask import Flask, send_from_directory

from api import answer as answer_module
from api import rank as rank_module

app = Flask(__name__)


@app.after_request
def add_cors(response):
    response.headers.update(
        {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        }
    )
    return response


@app.route("/")
def index():
    return send_from_directory(ROOT, "index.html")


@app.route("/style.css")
def style():
    return send_from_directory(ROOT, "style.css")


@app.route("/app.js")
def script():
    return send_from_directory(ROOT, "app.js")


app.add_url_rule("/api/rank", "rank", rank_module.rank_papers, methods=["POST", "OPTIONS"])
app.add_url_rule("/api/answer", "answer", answer_module.answer_question, methods=["POST", "OPTIONS"])

if __name__ == "__main__":
    threading.Timer(1.0, lambda: webbrowser.open("http://localhost:8000")).start()
    app.run(port=8000, debug=False)
