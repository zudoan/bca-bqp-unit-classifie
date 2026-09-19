from __future__ import annotations

import pytest

from matching.repository import InMemoryOrganizationRepository
from search.organization_search import OrganizationSearchService


ORGANIZATIONS = [
    {
        "organization_id": "BCA-HN-001",
        "organization_name": "Công an Thành phố Hà Nội",
        "normalized_name": "công an thành phố hà nội",
        "search_key": "cong an thanh pho ha noi",
        "organization_type_code": "PROVINCIAL_POLICE",
        "organization_level": "PROVINCE",
        "parent_organization_id": "BCA-CENTRAL-001",
        "province_name": "Hà Nội",
        "management": "BCA",
    },
    {
        "organization_id": "BCA-HN-002",
        "organization_name": "Đơn vị Chung",
        "normalized_name": "đơn vị chung",
        "search_key": "don vi chung",
        "organization_type_code": "DEPARTMENT",
        "organization_level": "PROVINCE",
        "parent_organization_id": "BCA-HN-001",
        "province_name": "Hà Nội",
        "management": "BCA",
    },
    {
        "organization_id": "BQP-DN-002",
        "organization_name": "Đơn vị Chung",
        "normalized_name": "đơn vị chung",
        "search_key": "don vi chung",
        "organization_type_code": "MILITARY_UNIT",
        "organization_level": "PROVINCE",
        "parent_organization_id": "BQP-CENTRAL-001",
        "province_name": "Đà Nẵng",
        "management": "BQP",
    },
    {
        "organization_id": "BQP-HN-003",
        "organization_name": "Ban Chỉ huy Quân sự huyện Sóc Sơn",
        "normalized_name": "ban chỉ huy quân sự huyện sóc sơn",
        "search_key": "ban chi huy quan su huyen soc son",
        "organization_type_code": "DISTRICT_MILITARY_COMMAND",
        "organization_level": "DISTRICT",
        "parent_organization_id": "BQP-HN-001",
        "province_name": "Hà Nội",
        "management": "BQP",
    },
    {
        "organization_id": "BQP-BN-004",
        "organization_name": "Bộ Chỉ huy Quân sự tỉnh Bắc Ninh",
        "normalized_name": "bộ chỉ huy quân sự tỉnh bắc ninh",
        "search_key": "bo chi huy quan su tinh bac ninh",
        "organization_type_code": "PROVINCIAL_MILITARY_COMMAND",
        "organization_level": "PROVINCE",
        "parent_organization_id": "BQP-CENTRAL-001",
        "province_name": "Bắc Ninh",
        "management": "BQP",
    },
    {
        "organization_id": "TEST-SHORT-001",
        "organization_name": "AB",
        "normalized_name": "ab",
        "search_key": "ab",
        "organization_type_code": "TEST",
        "organization_level": "TEST",
        "parent_organization_id": None,
        "province_name": "Hà Nội",
        "management": "BCA",
    },
]


ALIASES = [
    {
        "alias_id": 1,
        "organization_id": "BQP-HN-003",
        "alias_name": "BCHQS huyện Sóc Sơn",
        "normalized_alias": "bchqs huyện sóc sơn",
        "alias_search_key": "bchqs huyen soc son",
        "alias_type": "ABBREVIATION",
    },
    {
        "alias_id": 2,
        "organization_id": "BCA-HN-001",
        "alias_name": "CA TP Hà Nội",
        "normalized_alias": "ca tp hà nội",
        "alias_search_key": "ca tp ha noi",
        "alias_type": "SHORT_NAME",
    },
]


class TrackingRepository(InMemoryOrganizationRepository):
    def __init__(self):
        super().__init__(ORGANIZATIONS, ALIASES)
        self.management_lookup_count = 0

    def get_management(self, organization_id: str) -> str | None:
        self.management_lookup_count += 1
        return super().get_management(organization_id)


@pytest.fixture
def repository() -> TrackingRepository:
    return TrackingRepository()


@pytest.fixture
def search_service(repository: TrackingRepository) -> OrganizationSearchService:
    return OrganizationSearchService(repository)
