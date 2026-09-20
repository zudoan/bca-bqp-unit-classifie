from __future__ import annotations

from pathlib import Path
import unittest

import pandas as pd

from matching.repository import InMemoryOrganizationRepository
from matching.resolver import MatchingConfig
from preprocessing.normalize import normalize_name, to_search_key
from search.organization_search import OrganizationSearchService


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
