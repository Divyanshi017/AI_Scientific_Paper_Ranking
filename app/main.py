import uvicorn
from fastapi import FastAPI

from app.api.routes import register_api_routes

server = FastAPI(title="Research Paper Assistant", version="2.0.0")
register_api_routes(server)

# Vercel detects an ASGI application named `app` in app/main.py.
app = server

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)