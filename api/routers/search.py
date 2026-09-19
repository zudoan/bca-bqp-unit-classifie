"""Search API router — /api/search, /api/stats, /api/health, /api/normalize."""

from __future__ import annotations

from typing import Any

import pandas as pd
from fastapi import APIRouter, Request

from api.schemas import (
    HealthResponse,
    NormalizeResponse,
    SearchRequest,
    SearchResponse,
    StatsResponse,
)
from matching.resolver import MatchingConfig
from preprocessing.normalize import normalize_name, to_search_key

router = APIRouter(prefix="/api", tags=["search"])


# ── /api/health ──────────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()


# ── /api/stats ───────────────────────────────────────────────────────────────

@router.get("/stats", response_model=StatsResponse)
async def stats(request: Request) -> StatsResponse:
    df: pd.DataFrame = request.app.state.df
    return StatsResponse(
        total=len(df),
        bca_count=int((df["management"] == "BCA").sum()),
        bqp_count=int((df["management"] == "BQP").sum()),
        province_count=int(df["province_name"].nunique()),
        type_codes=sorted(df["organization_type_code"].unique().tolist()),
        provinces=sorted(df["province_name"].unique().tolist()),
    )


# ── /api/search ──────────────────────────────────────────────────────────────

@router.post("/search", response_model=SearchResponse)
async def search(body: SearchRequest, request: Request) -> dict[str, Any]:
    """Run the full matching pipeline and return results."""

    from matching.repository import InMemoryOrganizationRepository
    from search.organization_search import OrganizationSearchService

    # Build service with the requested fuzzy config ────────────────────────
    repo: InMemoryOrganizationRepository = request.app.state.repo
    config = MatchingConfig(
        fuzzy_scorer=body.fuzzy_scorer,
        fuzzy_minimum_score=body.fuzzy_threshold,
        fuzzy_top_k=body.fuzzy_top_k,
    )
    service = OrganizationSearchService(repo, config)

    result = service.search_organization(
        organization_id=body.organization_id,
        organization_name=body.organization_name,
        province_name=body.province_name,
        organization_type=body.organization_type,
    )

    # Enrich candidates with management if present
    if "candidates" in result and result["candidates"]:
        for c in result["candidates"]:
            org_id = c.get("organization_id")
            if org_id:
                try:
                    c["management"] = repo.get_management(org_id)
                except Exception:
                    c["management"] = None

    return result


# ── /api/normalize ───────────────────────────────────────────────────────────

@router.get("/normalize", response_model=NormalizeResponse)
async def normalize(q: str) -> NormalizeResponse:
    """Preview normalization without performing a search."""

    return NormalizeResponse(
        original=q,
        normalized=normalize_name(q),
        search_key=to_search_key(q),
    )
