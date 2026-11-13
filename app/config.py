import os
from dotenv import load_dotenv

load_dotenv()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
MAX_PAPERS = int(os.getenv("MAX_PAPERS", "50"))
TAVILY_RESULTS_PER_QUERY = 20
OPENALEX_MAILTO = os.getenv("OPENALEX_MAILTO", "research-paper-assistant@example.com").strip()