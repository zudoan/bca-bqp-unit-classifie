from __future__ import annotations

import pytest


pytest.importorskip("rapidfuzz")


def test_typo_returns_ranked_candidates_but_never_auto_resolves(
    search_service, repository
):
    result = search_service.search_organization(
        organization_name="Cong an thanh pho Ha Nio",
        province_name="Ha Noi",
    )

    assert result["match_status"] == "FUZZY_CANDIDATES"
    assert result["candidates"][0]["organization_id"] == "BCA-HN-001"
    assert "management" not in result
    assert all("management" not in item for item in result["candidates"])
    assert "top1_score" in result
    assert "score_margin" in result
    assert repository.management_lookup_count == 0


def test_candidate_blocking_is_strict(search_service, repository):
    result = search_service.search_organization(
        organization_name="Bo chi huy quan su tinh Bac Ninhh",
        province_name="Hà Nội",
    )

    assert result["match_status"] == "NOT_FOUND"
    assert repository.management_lookup_count == 0


def test_short_query_can_resolve_deterministically(search_service):
    result = search_service.search_organization(organization_name="AB")
    assert result["match_status"] == "EXACT_NAME_MATCH"
    assert result["organization_id"] == "TEST-SHORT-001"


def test_short_unknown_query_is_blocked_before_fuzzy(search_service, repository):
    result = search_service.search_organization(organization_name="XY")
    assert result["match_status"] == "INVALID_INPUT"
    assert result["reason"] == "QUERY_TOO_SHORT_FOR_FUZZY_MATCHING"
    assert repository.management_lookup_count == 0
