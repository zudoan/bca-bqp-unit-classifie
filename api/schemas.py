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
    fuzzy_scorer: str = Field(
        "WRatio",
        description="Thuật toán Fuzzy: WRatio | ratio | token_sort_ratio | token_set_ratio",
    )
    fuzzy_threshold: float = Field(
        85.0,
        ge=50,
        le=100,
        description="Ngưỡng điểm tối thiểu cho ứng viên fuzzy.",
    )
    fuzzy_top_k: int = Field(
        5,
        ge=1,
        le=20,
        description="Số ứng viên fuzzy tối đa.",
    )


# ── Response helpers ─────────────────────────────────────────────────────────

class CandidateItem(BaseModel):
    organization_id: str
    organization_name: str
    province_name: str | None = None
    organization_type_code: str = ""
    organization_level: str | None = None
    parent_organization_id: str | None = None
    score: float | int | None = None
    matched_on: str | None = None
    management: str | None = None


class SearchResponse(BaseModel):
    """Unified response envelope for every match status."""

    match_status: str
    match_score: float | int | None = None
    organization_id: str | None = None
    organization_name: str | None = None
    province_name: str | None = None
    organization_type_code: str | None = None
    management: str | None = None
    candidates: list[CandidateItem] | None = None
    top1_score: float | int | None = None
    top2_score: float | int | None = None
    score_margin: float | None = None
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
