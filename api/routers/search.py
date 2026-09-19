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
    """Run the strict deterministic matching pipeline and return binary result."""

    from matching.repository import InMemoryOrganizationRepository
    from search.organization_search import OrganizationSearchService

    repo: InMemoryOrganizationRepository = request.app.state.repo
    config = MatchingConfig(strict_mode=True)
    service = OrganizationSearchService(repo, config)

    result = service.search_organization(
        organization_id=body.organization_id,
        organization_name=body.organization_name,
        province_name=body.province_name,
        organization_type=body.organization_type,
    )

    is_match = bool(result.get("management"))
    return {
        "status": "MATCH_100" if is_match else "UNKNOWN",
        "match_status": result.get("match_status", "UNKNOWN"),
        "match_score": 100 if is_match else None,
        "organization_id": result.get("organization_id"),
        "organization_name": result.get("organization_name"),
        "province_name": result.get("province_name"),
        "organization_type_code": result.get("organization_type_code"),
        "management": result.get("management"),
        "message": None if is_match else "Không có dữ liệu cho đơn vị này trong hệ thống BCA / BQP.",
        "reason": result.get("reason"),
        "errors": result.get("errors"),
    }


# ── /api/normalize ───────────────────────────────────────────────────────────

@router.get("/normalize", response_model=NormalizeResponse)
async def normalize(q: str) -> NormalizeResponse:
    """Preview normalization without performing a search."""

    return NormalizeResponse(
        original=q,
        normalized=normalize_name(q),
        search_key=to_search_key(q),
    )
