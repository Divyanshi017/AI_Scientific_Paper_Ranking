import os
from dotenv import load_dotenv

load_dotenv()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
MAX_PAPERS = int(os.getenv("MAX_PAPERS", "50"))  # upper cap only; Tavily usually yields fewer
TAVILY_RESULTS_PER_QUERY = 20