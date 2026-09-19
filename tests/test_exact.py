from __future__ import annotations


def test_exact_id_is_strongest_and_then_management_is_looked_up(
    search_service, repository
):
    result = search_service.search_organization(organization_id="BCA-HN-001")

    assert result == {
        "match_status": "EXACT_ID_MATCH",
        "match_score": 100,
        "organization_id": "BCA-HN-001",
        "organization_name": "Công an Thành phố Hà Nội",
        "province_name": "Hà Nội",
        "organization_type_code": "PROVINCIAL_POLICE",
        "management": "BCA",
    }
    assert repository.management_lookup_count == 1


def test_exact_id_honors_strict_context(search_service, repository):
    result = search_service.search_organization(
        organization_id="BCA-HN-001", province_name="Đà Nẵng"
    )

    assert result["match_status"] == "NOT_FOUND"
    assert result["reason"] == "DETERMINISTIC_MATCH_CONTEXT_MISMATCH"
    assert repository.management_lookup_count == 0


def test_exact_canonical_name(search_service):
    result = search_service.search_organization(
        organization_name="Công an Thành phố Hà Nội"
    )
    assert result["match_status"] == "EXACT_NAME_MATCH"
    assert result["organization_id"] == "BCA-HN-001"


def test_uppercase_and_outer_spaces_are_normalized_not_raw_exact(search_service):
    result = search_service.search_organization(
        organization_name="  CÔNG AN THÀNH PHỐ HÀ NỘI  "
    )
    assert result["match_status"] == "NORMALIZED_MATCH"
    assert result["organization_id"] == "BCA-HN-001"


def test_unaccented_name_uses_deterministic_search_key(search_service):
    result = search_service.search_organization(
        organization_name="Cong an Thanh pho Ha Noi"
    )
    assert result["match_status"] == "SEARCH_KEY_MATCH"
    assert result["organization_id"] == "BCA-HN-001"


def test_alias_is_resolved_before_fuzzy(search_service):
    result = search_service.search_organization(
        organization_name="BCHQS huyện Sóc Sơn"
    )
    assert result["match_status"] == "ALIAS_MATCH"
    assert result["organization_id"] == "BQP-HN-003"
    assert result["management"] == "BQP"


def test_duplicate_name_without_context_is_ambiguous_and_has_no_management(
    search_service, repository
):
    result = search_service.search_organization(organization_name="Đơn vị Chung")

    assert result["match_status"] == "AMBIGUOUS_MATCH"
    assert [item["organization_id"] for item in result["candidates"]] == [
        "BCA-HN-002",
        "BQP-DN-002",
    ]
    assert all("management" not in item for item in result["candidates"])
    assert repository.management_lookup_count == 0


def test_province_disambiguates_duplicate_name(search_service):
    result = search_service.search_organization(
        organization_name="Đơn vị Chung", province_name="Da Nang"
    )
    assert result["match_status"] == "EXACT_NAME_MATCH"
    assert result["organization_id"] == "BQP-DN-002"
    assert result["management"] == "BQP"


def test_type_disambiguates_duplicate_name(search_service):
    result = search_service.search_organization(
        organization_name="Đơn vị Chung", organization_type="department"
    )
    assert result["organization_id"] == "BCA-HN-002"


def test_wrong_context_does_not_fall_through_to_fuzzy(search_service, repository):
    result = search_service.search_organization(
        organization_name="Đơn vị Chung", province_name="Bắc Ninh"
    )
    assert result["match_status"] == "NOT_FOUND"
    assert result["reason"] == "DETERMINISTIC_MATCH_CONTEXT_MISMATCH"
    assert repository.management_lookup_count == 0
