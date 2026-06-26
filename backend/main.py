"""
TRIPZ-AI Backend — FastAPI Application Entry Point
"""

import logging
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (parent of backend/) or CWD
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv()  # fallback to CWD

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.trip_router import router
from api.sessions_router import router as sessions_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
logging.getLogger("tripz.agents").setLevel(logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)

app = FastAPI(
    title="TRIPZ-AI Backend",
    description="Multi-Agent AI Travel Operating System powered by LangGraph + Ollama",
    version="1.0.0",
)

# CORS — allow local dev + any origins from CORS_ORIGINS env var (comma-separated)
_cors_origins = ["http://localhost:3000", "http://localhost:3001"]
_extra = os.environ.get("CORS_ORIGINS", "").strip()
if _extra:
    _cors_origins.extend([o.strip() for o in _extra.split(",") if o.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(sessions_router)


@app.get("/")
async def root():
    return {
        "service": "TRIPZ-AI",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "plan_stream": "POST /api/v1/plan/stream  (SSE)",
            "plan_rest":   "POST /api/v1/plan         (JSON)",
            "health":      "GET  /api/v1/health",
        },
    }
