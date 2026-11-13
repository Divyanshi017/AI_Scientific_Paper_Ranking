from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import register_api_routes

STATIC_DIR = Path(__file__).parent / "static"

server = FastAPI(title="Zenshin", version="2.0.0")
register_api_routes(server)
server.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@server.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


# Vercel detects an ASGI application named `app` in app/main.py.
app = server

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
