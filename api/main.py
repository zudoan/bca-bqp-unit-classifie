"""FastAPI wrapper around the organization search service.

This file adds ZERO new matching logic. It only exposes
search.organization_search.OrganizationSearchService as HTTP endpoints, so
the exact-first, conservative-fuzzy, and payroll-first guarantees apply here
unchanged.
"""
from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from matching.repository import InMemoryOrganizationRepository
from matching.resolver import MatchingConfig
from search.batch_processing import BatchProcessingError, process_batch_file
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
service = OrganizationSearchService(repo, MatchingConfig())

app = FastAPI(
    title="BCA/BQP Organization Registry API",
    description=(
        "Exact-first organization resolution with conservative fuzzy fallback, "
        "followed by payroll-first and BCA/BQP management lookup."
    ),
    version="1.0.0",
)

cors_origins = [
    origin.strip().rstrip("/")
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://localhost:3000",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    expose_headers=[
        "Content-Disposition",
        "X-Batch-Input-Count",
        "X-Batch-Paid-Count",
        "X-Batch-Not-Paid-Count",
        "X-Batch-Unresolved-Count",
    ],
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


MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@app.post(
    "/api/v1/organizations/batch",
    summary="Phân loại danh sách đơn vị từ Excel hoặc Word",
    responses={
        200: {
            "content": {"application/zip": {}},
            "description": "ZIP chứa hai file: được trả lương và không được trả lương.",
        }
    },
)
async def batch_search(
    file: UploadFile = File(...),
    column_name: Optional[str] = Form(None, max_length=128),
):
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    await file.close()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail="File vượt giới hạn 10 MB.",
        )

    try:
        artifact = await run_in_threadpool(
            process_batch_file,
            file.filename or "",
            content,
            service,
            column_name.strip() if column_name and column_name.strip() else None,
        )
    except BatchProcessingError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    encoded_name = quote(artifact.archive_name)
    headers = {
        "Content-Disposition": (
            f'attachment; filename="batch-results.zip"; filename*=UTF-8\'\'{encoded_name}'
        ),
        "X-Batch-Input-Count": str(artifact.input_count),
        "X-Batch-Paid-Count": str(artifact.paid_count),
        "X-Batch-Not-Paid-Count": str(artifact.not_paid_count),
        "X-Batch-Unresolved-Count": str(artifact.unresolved_count),
    }
    return StreamingResponse(
        BytesIO(artifact.archive),
        media_type="application/zip",
        headers=headers,
    )


@app.get("/api/v1/organizations/{organization_id}")
def get_by_id(organization_id: str):
    organization = repo.get_by_id(organization_id)
    if organization is None:
        raise HTTPException(status_code=404, detail="ORGANIZATION_ID_NOT_FOUND")
    management = repo.get_management(organization_id)
    payroll = repo.get_payroll(organization_id)
    return {
        "organization_id": organization.organization_id,
        "organization_name": organization.organization_name,
        "province_name": organization.province_name,
        "organization_type_code": organization.organization_type_code,
        "paying_organization": payroll.paying_organization if payroll else None,
        "payroll_status": payroll.payroll_status if payroll else None,
        "management": management,
    }
