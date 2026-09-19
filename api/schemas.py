"""Pydantic models for the FastAPI search contract."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ── Request ──────────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    """Body of ``POST /api/search``."""

    organization_name: str | None = Field(
        None,
        max_length=512,
        description="Tên tổ chức cần tra cứu (có dấu / không dấu / viết tắt).",
        examples=["Công an tỉnh Thái Bình"],
    )
    organization_id: str | None = Field(
        None,
        max_length=128,
        description="Mã tổ chức nếu biết chính xác.",
        examples=["BCA-PROVINCE-002153"],
    )
    province_name: str | None = Field(
        None,
        max_length=128,
        description="Tỉnh / Thành phố để thu hẹp phạm vi tra cứu.",
        examples=["Thái Bình"],
    )
    organization_type: str | None = Field(
        None,
        max_length=128,
        description="Loại tổ chức (mã).",
        examples=["POLICE_PROVINCE"],
    )


# ── Response ─────────────────────────────────────────────────────────────────

class SearchResponse(BaseModel):
    """Unified binary response: MATCH_100 or UNKNOWN."""

    status: str = Field(description="Kết quả: MATCH_100 hoặc UNKNOWN")
    match_status: str = Field(description="Trạng thái so khớp kỹ thuật")
    match_score: int | None = Field(None, description="100 nếu đúng chính xác")
    organization_id: str | None = None
    organization_name: str | None = None
    province_name: str | None = None
    organization_type_code: str | None = None
    management: str | None = Field(None, description="BCA hoặc BQP")
    message: str | None = None
    reason: str | None = None
    errors: list[str] | None = None


class StatsResponse(BaseModel):
    total: int
    bca_count: int
    bqp_count: int
    province_count: int
    type_codes: list[str]
    provinces: list[str]


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"


class NormalizeResponse(BaseModel):
    """Response for the normalization preview endpoint."""

    original: str
    normalized: str
    search_key: str
