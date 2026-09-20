"""FastAPI wrapper around the existing strict-deterministic search service.

This file adds ZERO new matching logic. It only exposes
search.organization_search.OrganizationSearchService as HTTP endpoints, so
whatever guarantees the Gradio app already has (no fuzzy auto-assignment,
UNKNOWN when unsure) apply here unchanged.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from matching.repository import InMemoryOrganizationRepository
from matching.resolver import MatchingConfig
from search.organization_search import OrganizationSearchService

_ROOT = Path(__file__).resolve().parent.parent
DATASET_PATH = _ROOT / "data" / "dataset.csv"
ALIASES_PATH = _ROOT / "data" / "aliases.csv"

df = pd.read_csv(DATASET_PATH, dtype=str, keep_default_na=False)
rows = df.to_dict("records")
aliases = (
    pd.read_csv(ALIASES_PATH, dtype=str, keep_default_na=False).to_dict("records")
    if ALIASES_PATH.is_file()
    else []
)
repo = InMemoryOrganizationRepository(rows, aliases)
service = OrganizationSearchService(repo, MatchingConfig(strict_mode=True))

app = FastAPI(
    title="BCA/BQP Organization Registry API",
    description="Strict Deterministic Entity Resolution — 100% match or UNKNOWN, never a guess.",
    version="1.0.0",
)


class SearchRequest(BaseModel):
    organization_id: Optional[str] = Field(None, max_length=128)
    organization_name: Optional[str] = Field(None, max_length=512)
    province_name: Optional[str] = Field(None, max_length=128)
    organization_type: Optional[str] = Field(None, max_length=128)


@app.get("/health")
def health():
    return {"status": "ok", "total_organizations": len(df)}


@app.post("/api/v1/organizations/search")
def search(payload: SearchRequest):
    return service.search_organization(
        organization_id=payload.organization_id,
        organization_name=payload.organization_name,
        province_name=payload.province_name,
        organization_type=payload.organization_type,
    )


@app.get("/api/v1/organizations/search")
def search_get(
    organization_name: Optional[str] = Query(None),
    organization_id: Optional[str] = Query(None),
    province_name: Optional[str] = Query(None),
    organization_type: Optional[str] = Query(None),
):
    return service.search_organization(
        organization_id=organization_id,
        organization_name=organization_name,
        province_name=province_name,
        organization_type=organization_type,
    )


@app.get("/api/v1/organizations/{organization_id}")
def get_by_id(organization_id: str):
    organization = repo.get_by_id(organization_id)
    if organization is None:
        raise HTTPException(status_code=404, detail="ORGANIZATION_ID_NOT_FOUND")
    management = repo.get_management(organization_id)
    return {
        "organization_id": organization.organization_id,
        "organization_name": organization.organization_name,
        "province_name": organization.province_name,
        "organization_type_code": organization.organization_type_code,
        "management": management,
    }
