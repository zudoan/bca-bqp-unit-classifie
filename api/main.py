"""FastAPI application — Organization Matching Registry.

Start with:
    python run.py
Or:
    uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from matching.repository import InMemoryOrganizationRepository
from api.routers.search import router as search_router

# ── Paths ────────────────────────────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_PATH = _PROJECT_ROOT / "data" / "dataset.csv"
ALIASES_PATH = _PROJECT_ROOT / "data" / "test" / "aliases.csv"
STATIC_DIR = Path(__file__).resolve().parent / "static"


# ── Lifespan — load data once on startup ─────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the CSV dataset and build the in-memory repository at startup."""

    print("[INFO] Loading dataset ...")
    df = pd.read_csv(DATASET_PATH, dtype=str, keep_default_na=False)
    rows = df.to_dict("records")

    aliases: list[dict] = []
    if ALIASES_PATH.is_file():
        aliases = pd.read_csv(ALIASES_PATH, dtype=str, keep_default_na=False).to_dict("records")

    repo = InMemoryOrganizationRepository(rows, aliases)
    app.state.df = df
    app.state.repo = repo

    total = len(df)
    bca = int((df["management"] == "BCA").sum())
    bqp = int((df["management"] == "BQP").sum())
    print(f"[INFO] Registry loaded: {total:,} organizations ({bca:,} BCA, {bqp:,} BQP)")

    yield  # app runs

    print("[INFO] Shutting down ...")


# ── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Organization Matching Registry — BCA / BQP",
    description="Entity resolution API: Nhập tên/mã tổ chức → tìm đúng tổ chức → tra cứu BCA hay BQP.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow all origins so the link works from any browser
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(search_router)

# Static files (CSS, JS)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── Root: serve index.html ───────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def root():
    return FileResponse(str(STATIC_DIR / "index.html"))
