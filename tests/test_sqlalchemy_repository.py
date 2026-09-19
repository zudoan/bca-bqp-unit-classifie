from __future__ import annotations

import pytest


sa = pytest.importorskip("sqlalchemy")

from matching.repository import SqlAlchemyOrganizationRepository
from search.organization_search import OrganizationSearchService


def test_sqlalchemy_adapter_keeps_matching_and_management_queries_separate():
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    metadata = sa.MetaData()
    organizations = sa.Table(
        "organizations",
        metadata,
        sa.Column("organization_id", sa.String, primary_key=True),
        sa.Column("organization_name", sa.String, nullable=False),
        sa.Column("normalized_name", sa.String, nullable=False),
        sa.Column("search_key", sa.String, nullable=False),
        sa.Column("organization_type_code", sa.String, nullable=False),
        sa.Column("organization_level", sa.String),
        sa.Column("parent_organization_id", sa.String),
        sa.Column("province_name", sa.String),
        sa.Column("management", sa.String, nullable=False),
    )
    aliases = sa.Table(
        "organization_aliases",
        metadata,
        sa.Column("alias_id", sa.Integer, primary_key=True),
        sa.Column("organization_id", sa.String, nullable=False),
        sa.Column("alias_name", sa.String, nullable=False),
        sa.Column("normalized_alias", sa.String, nullable=False),
        sa.Column("alias_search_key", sa.String, nullable=False),
        sa.Column("alias_type", sa.String, nullable=False),
    )
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            organizations.insert(),
            {
                "organization_id": "BCA-001",
                "organization_name": "Công an tỉnh Demo",
                "normalized_name": "công an tỉnh demo",
                "search_key": "cong an tinh demo",
                "organization_type_code": "PROVINCIAL_POLICE",
                "organization_level": "PROVINCE",
                "province_name": "Hà Nội",
                "management": "BCA",
            },
        )
        connection.execute(
            aliases.insert(),
            {
                "alias_id": 1,
                "organization_id": "BCA-001",
                "alias_name": "CA tỉnh Demo",
                "normalized_alias": "ca tỉnh demo",
                "alias_search_key": "ca tinh demo",
                "alias_type": "SHORT_NAME",
            },
        )

    repository = SqlAlchemyOrganizationRepository.from_engine(engine)
    service = OrganizationSearchService(repository)

    result = service.search_organization(organization_name="CA tinh Demo")
    assert result["match_status"] == "ALIAS_MATCH"
    assert result["management"] == "BCA"

    fuzzy_result = service.search_organization(
        organization_name="Cong an tinh Demmo",
        province_name="Ha Noi",
    )
    assert fuzzy_result["match_status"] == "FUZZY_CANDIDATES"
    assert fuzzy_result["candidates"][0]["organization_id"] == "BCA-001"
    assert "management" not in fuzzy_result
