from __future__ import annotations

import inspect

from search.management_lookup import lookup_management
from search.organization_search import configure_repository, search_organization


def test_empty_query_is_invalid(search_service, repository):
    result = search_service.search_organization()
    assert result["match_status"] == "INVALID_INPUT"
    assert repository.management_lookup_count == 0


def test_non_string_input_is_invalid(search_service):
    result = search_service.search_organization(organization_name=123)
    assert result["match_status"] == "INVALID_INPUT"
    assert "organization_name must be a string" in result["errors"]


def test_nul_input_is_rejected_before_database_matching(
    search_service, repository
):
    result = search_service.search_organization(
        organization_name="Công an\x00Hà Nội"
    )
    assert result["match_status"] == "INVALID_INPUT"
    assert "NUL" in result["errors"][0]
    assert repository.management_lookup_count == 0


def test_unknown_id_without_name_is_not_found(search_service, repository):
    result = search_service.search_organization(organization_id="UNKNOWN")
    assert result["match_status"] == "NOT_FOUND"
    assert repository.management_lookup_count == 0


def test_unknown_id_can_fall_back_to_provided_name(search_service):
    result = search_service.search_organization(
        organization_id="UNKNOWN",
        organization_name="Công an Thành phố Hà Nội",
    )
    assert result["match_status"] == "EXACT_NAME_MATCH"
    assert result["organization_id"] == "BCA-HN-001"


def test_public_function_has_version_one_signature():
    assert list(inspect.signature(search_organization).parameters) == [
        "organization_id",
        "organization_name",
        "province_name",
        "organization_type",
    ]


def test_public_facade_uses_configured_repository(repository):
    configure_repository(repository)
    result = search_organization(organization_id="BQP-HN-003")
    assert result["organization_id"] == "BQP-HN-003"
    assert result["management"] == "BQP"


def test_management_lookup_is_an_explicit_separate_operation(repository):
    assert lookup_management(repository, "BCA-HN-001") == "BCA"
    assert repository.management_lookup_count == 1
