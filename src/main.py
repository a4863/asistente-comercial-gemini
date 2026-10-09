from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.dashboard_router import router as dashboard_router
from src.api.drafts_router import router as drafts_router

app = FastAPI(
    title="ACLIMAR Assistant API",
    description="Cockpit local de apoyo a la toma de decisiones comerciales. Local-only (127.0.0.1).",
    version="1.0.0",
)

# Restricción: CORS configurado para frontends locales en 127.0.0.1 / localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(dashboard_router)
app.include_router(drafts_router)


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "bind": "127.0.0.1"}
