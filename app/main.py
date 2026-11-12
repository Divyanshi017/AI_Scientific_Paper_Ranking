import uvicorn
from fastapi import FastAPI
from dash import Dash

from app.api.routes import register_api_routes
from app.frontend.layout import build_layout
from app.frontend.callbacks import register_callbacks

# FastAPI serves both the REST API and the Dash Python-authored interface.
server = FastAPI(title="Research Paper Assistant", version="2.0.0")
register_api_routes(server)

dash_app = Dash(
    backend="fastapi",
    server=server,
    title="Research Paper Assistant",
    update_title="Working...",
    suppress_callback_exceptions=True,
)
dash_app.layout = build_layout()
register_callbacks(dash_app)

# Vercel detects an ASGI application named `app` in app/main.py.
app = server

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
