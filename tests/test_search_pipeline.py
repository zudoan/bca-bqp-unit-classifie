from __future__ import annotations

from pathlib import Path
import os
import unittest

import pandas as pd

from matching.acronym_match import AcronymDatasetError, AcronymMatcher
from matching.repository import InMemoryOrganizationRepository
from matching.resolver import MatchingConfig
from preprocessing.normalize import normalize_name, to_search_key
from search.organization_search import OrganizationSearchService

os.environ["CORS_ORIGINS"] = "https://bca-bqp-frontend.onrender.com/"

from api.main import app
from fastapi.testclient import TestClient


def make_organization(
    organization_id: str,
    name: str,
    *,
    province: str = "Hà Nội",
    management: str = "BCA",
    paying_organization: str = "BCA",
    payroll_status: str = "Do BCA trả lương",
) -> dict[str, str]:
    return {
        "organization_id": organization_id,
        "organization_name": name,
        "organization_name_normalized": normalize_name(name),
        "organization_name_search_key": to_search_key(name),
        "organization_type_code": "TEST_UNIT",
        "organization_level": "TEST",
        "parent_organization_id": "",
        "province_name": province,
        "management": management,
        "co_quan_tra_luong": paying_organization,
        "trang_thai_tra_luong": payroll_status,
    }


class SearchPipelineTests(unittest.TestCase):
    def test_acronym_alias_is_a_deterministic_match(self) -> None:
        canonical_name = "C\u00f4ng an Th\u00e0nh ph\u1ed1 H\u1ed3 Ch\u00ed Minh"
        repository = InMemoryOrganizationRepository(
            [
                make_organization(
                    "ORG-ACRONYM-001",
                    canonical_name,
                    province="Th\u00e0nh ph\u1ed1 H\u1ed3 Ch\u00ed Minh",
                )
            ]
        )
        matcher = AcronymMatcher(
            repository,
            [
                {"alias": "CA TP HCM", "label": canonical_name},
                {"alias": "C\u00f4ng an TP HCM", "label": canonical_name},
            ],
        )
        service = OrganizationSearchService(
            repository,
            MatchingConfig(strict_mode=True),
            matcher,
        )

        result = service.search_organization(
            organization_name="ca-tp.hcm"
        )

        self.assertEqual(result["match_status"], "ACRONYM_MATCH")
        self.assertEqual(result["organization_id"], "ORG-ACRONYM-001")
        self.assertEqual(result["match_score"], 100)

    def test_conflicting_acronym_uses_context_disambiguation(self) -> None:
        first_name = "C\u00f4ng an huy\u1ec7n Minh An"
        second_name = "Ban ch\u1ec9 huy qu\u00e2n s\u1ef1 Minh An"
        repository = InMemoryOrganizationRepository(
            [
                make_organization(
                    "ORG-ACRONYM-002", first_name, province="T\u1ec9nh A"
                ),
                make_organization(
                    "ORG-ACRONYM-003", second_name, province="T\u1ec9nh B"
                ),
            ]
        )
        matcher = AcronymMatcher(
            repository,
            [
                {"alias": "DV MA", "label": first_name},
                {"alias": "DV MA", "label": second_name},
            ],
        )
        service = OrganizationSearchService(repository, acronym_matcher=matcher)

        ambiguous = service.search_organization(organization_name="DV MA")
        resolved = service.search_organization(
            organization_name="DV MA", province_name="Tinh B"
        )

        self.assertEqual(ambiguous["match_status"], "AMBIGUOUS_MATCH")
        self.assertEqual(len(ambiguous["candidates"]), 2)
        self.assertEqual(resolved["match_status"], "ACRONYM_MATCH")
        self.assertEqual(resolved["organization_id"], "ORG-ACRONYM-003")

    def test_acronym_label_must_exist_in_registry(self) -> None:
        repository = InMemoryOrganizationRepository(
            [make_organization("ORG-ACRONYM-004", "T\u1ed5 ch\u1ee9c c\u00f3 th\u1eadt")]
        )

        with self.assertRaises(AcronymDatasetError):
            AcronymMatcher(
                repository,
                [{"alias": "TCG", "label": "T\u1ed5 ch\u1ee9c kh\u00f4ng t\u1ed3n t\u1ea1i"}],
            )

    def test_api_uses_real_acronym_dataset(self) -> None:
        examples = {
            "CA TP HCM": "BCA-PROVINCE-009777",
            "C\u00f4ng an TP HCM": "BCA-PROVINCE-009777",
            "CA HN": "BCA-PROVINCE-000035",
            "C\u00f4ng an HN": "BCA-PROVINCE-000035",
        }
        client = TestClient(app)

        for query, expected_id in examples.items():
            with self.subTest(query=query):
                response = client.post(
                    "/api/v1/organizations/search",
                    json={"organization_name": query},
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response.json()["match_status"], "ACRONYM_MATCH"
                )
                self.assertEqual(
                    response.json()["organization_id"], expected_id
                )

        health = client.get("/health").json()
        self.assertGreater(health["acronym_aliases"], 0)

    def test_render_frontend_cors_preflight(self) -> None:
        client = TestClient(app)

        response = client.options(
            "/api/v1/organizations/search",
            headers={
                "Origin": "https://bca-bqp-frontend.onrender.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            "https://bca-bqp-frontend.onrender.com",
        )

    def test_payroll_and_management_are_independent(self) -> None:
        row = make_organization(
            "ORG-001",
            "Cục Kiểm tra dữ liệu",
            management="BCA",
            paying_organization="BQP",
            payroll_status="Do BQP trả lương",
        )
        service = OrganizationSearchService(InMemoryOrganizationRepository([row]))

        result = service.search_organization(organization_id="ORG-001")

        self.assertEqual(result["match_status"], "EXACT_ID_MATCH")
        self.assertEqual(result["paying_organization"], "BQP")
        self.assertEqual(result["payroll_status"], "Do BQP trả lương")
        self.assertEqual(result["management"], "BCA")

    def test_blank_payer_is_not_inferred(self) -> None:
        row = make_organization(
            "ORG-002",
            "Đơn vị chưa xác định nguồn lương",
            paying_organization="",
            payroll_status="Không do BCA/BQP trả lương",
        )
        service = OrganizationSearchService(InMemoryOrganizationRepository([row]))

        result = service.search_organization(organization_id="ORG-002")

        self.assertIsNone(result["paying_organization"])
        self.assertEqual(result["management"], "BCA")

    def test_high_confidence_fuzzy_match_resolves(self) -> None:
        rows = [
            make_organization("ORG-003", "Công an tỉnh Thái Bình", province="Thái Bình"),
            make_organization("ORG-004", "Bệnh viện Quân y Trung ương", management="BQP"),
        ]
        service = OrganizationSearchService(InMemoryOrganizationRepository(rows))

        result = service.search_organization(
            organization_name="Cong an tinh Thai Binhh",
            province_name="Thái Bình",
        )

        self.assertEqual(result["match_status"], "FUZZY_MATCH")
        self.assertEqual(result["organization_id"], "ORG-003")
        self.assertGreaterEqual(result["match_score"], 93)

    def test_close_fuzzy_results_require_review(self) -> None:
        rows = [
            make_organization("ORG-005", "Công an huyện Châu Thành", province="Tây Ninh"),
            make_organization("ORG-006", "Công an huyện Châu Thanh", province="Long An"),
        ]
        service = OrganizationSearchService(InMemoryOrganizationRepository(rows))

        result = service.search_organization(organization_name="Cong an huyen Chau Thah")

        self.assertEqual(result["match_status"], "FUZZY_CANDIDATES")
        self.assertGreaterEqual(len(result["candidates"]), 2)
        self.assertNotIn("management", result)
        self.assertNotIn("paying_organization", result)

    def test_strict_mode_disables_fuzzy(self) -> None:
        row = make_organization("ORG-007", "Công an tỉnh Thái Bình")
        service = OrganizationSearchService(
            InMemoryOrganizationRepository([row]),
            MatchingConfig(strict_mode=True),
        )

        result = service.search_organization(organization_name="Cong an tinh Thai Binhh")

        self.assertEqual(result["match_status"], "NOT_FOUND")


class RealRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = Path(__file__).resolve().parent.parent
        cls.dataframe = pd.read_csv(
            root / "data" / "dataset.csv",
            dtype=str,
            keep_default_na=False,
        )
        aliases = pd.read_csv(
            root / "data" / "aliases.csv",
            dtype=str,
            keep_default_na=False,
        ).to_dict("records")
        cls.service = OrganizationSearchService(
            InMemoryOrganizationRepository(
                cls.dataframe.to_dict("records"),
                aliases,
            )
        )

    def test_registry_schema_and_invariants(self) -> None:
        required_columns = {
            "organization_id",
            "organization_name",
            "management",
            "co_quan_tra_luong",
            "trang_thai_tra_luong",
        }
        self.assertTrue(required_columns.issubset(self.dataframe.columns))
        self.assertFalse(self.dataframe["organization_id"].duplicated().any())
        self.assertFalse(
            self.dataframe["trang_thai_tra_luong"].str.strip().eq("").any()
        )
        self.assertTrue(set(self.dataframe["management"]) <= {"BCA", "BQP"})

    def test_real_cross_domain_payroll_record(self) -> None:
        result = self.service.search_organization(
            organization_id="BCA-CENTRAL-000003"
        )

        self.assertEqual(result["organization_name"], "Cục Đào tạo")
        self.assertEqual(result["paying_organization"], "BQP")
        self.assertEqual(result["payroll_status"], "Do BQP trả lương")
        self.assertEqual(result["management"], "BCA")

    def test_real_fuzzy_typo(self) -> None:
        result = self.service.search_organization(
            organization_name="Cuc Dao taoo",
            province_name="Hà Nội",
            organization_type="MINISTRY_DEPARTMENT",
        )

        self.assertEqual(result["match_status"], "FUZZY_MATCH")
        self.assertEqual(result["organization_id"], "BCA-CENTRAL-000003")


if __name__ == "__main__":
    unittest.main()
