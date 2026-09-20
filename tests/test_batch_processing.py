from __future__ import annotations

from io import BytesIO
import os
from pathlib import Path
import unittest
from zipfile import ZipFile

import pandas as pd
from docx import Document
from docx.enum.section import WD_ORIENT
from fastapi.testclient import TestClient
from openpyxl import Workbook, load_workbook

os.environ["CORS_ORIGINS"] = "https://bca-bqp-frontend.onrender.com/"

from api.main import app
from matching.repository import InMemoryOrganizationRepository
from matching.resolver import MatchingConfig
from search.batch_processing import process_batch_file
from search.organization_search import OrganizationSearchService


ROOT = Path(__file__).resolve().parent.parent


def make_service() -> OrganizationSearchService:
    rows = pd.read_csv(
        ROOT / "data" / "dataset.csv", dtype=str, keep_default_na=False
    ).to_dict("records")
    aliases = pd.read_csv(
        ROOT / "data" / "aliases.csv", dtype=str, keep_default_na=False
    ).to_dict("records")
    return OrganizationSearchService(
        InMemoryOrganizationRepository(rows, aliases), MatchingConfig()
    )


def make_excel_input() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Đơn vị"
    sheet.append(["Tên đơn vị"])
    sheet.append(["Công an tỉnh Thái Bình"])
    sheet.append(["Cục Tổ chức cán bộ"])
    sheet.append(["Đơn vị hoàn toàn không tồn tại 12345"])
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def make_word_input() -> bytes:
    document = Document()
    document.add_heading("Danh sách đầu vào", level=1)
    table = document.add_table(rows=1, cols=1)
    table.cell(0, 0).text = "Tên tổ chức"
    for name in (
        "Công an tỉnh Thái Bình",
        "Cục Tổ chức cán bộ",
        "Đơn vị hoàn toàn không tồn tại 12345",
    ):
        table.add_row().cells[0].text = name
    output = BytesIO()
    document.save(output)
    return output.getvalue()


class BatchProcessingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.service = make_service()

    def test_excel_creates_two_workbooks_and_keeps_unresolved_separate(self) -> None:
        artifact = process_batch_file(
            "input.xlsx", make_excel_input(), self.service
        )

        self.assertEqual(artifact.input_count, 3)
        self.assertEqual(artifact.paid_count, 1)
        self.assertEqual(artifact.not_paid_count, 1)
        self.assertEqual(artifact.unresolved_count, 1)

        with ZipFile(BytesIO(artifact.archive)) as archive:
            names = sorted(archive.namelist())
            self.assertEqual(
                names,
                [
                    "input_duoc_tra_luong.xlsx",
                    "input_khong_duoc_tra_luong.xlsx",
                ],
            )
            paid_book = load_workbook(BytesIO(archive.read(names[0])), data_only=True)
            not_paid_book = load_workbook(BytesIO(archive.read(names[1])), data_only=True)

        self.assertIn("Công an tỉnh Thái Bình", paid_book["Được trả lương"][5][1].value)
        self.assertEqual(paid_book["Được trả lương"].freeze_panes, "A5")
        self.assertFalse(paid_book["Được trả lương"].sheet_view.showGridLines)
        self.assertEqual(paid_book["Được trả lương"]["A1"].fill.fgColor.rgb, "00163A5F")
        self.assertEqual(
            not_paid_book.sheetnames,
            ["Không được trả lương", "Chưa thể kết luận"],
        )
        self.assertIn("Cục Tổ chức cán bộ", not_paid_book["Không được trả lương"][5][1].value)
        self.assertIn(
            "Đơn vị hoàn toàn không tồn tại",
            not_paid_book["Chưa thể kết luận"][2][1].value,
        )

    def test_word_creates_two_documents_with_unresolved_appendix(self) -> None:
        artifact = process_batch_file("input.docx", make_word_input(), self.service)

        self.assertEqual(
            (artifact.paid_count, artifact.not_paid_count, artifact.unresolved_count),
            (1, 1, 1),
        )
        with ZipFile(BytesIO(artifact.archive)) as archive:
            names = sorted(archive.namelist())
            self.assertEqual(len(names), 2)
            paid = Document(BytesIO(archive.read("input_duoc_tra_luong.docx")))
            not_paid = Document(BytesIO(archive.read("input_khong_duoc_tra_luong.docx")))

        paid_text = "\n".join(
            cell.text
            for table in paid.tables
            for row in table.rows
            for cell in row.cells
        )
        not_paid_text = "\n".join(
            [paragraph.text for paragraph in not_paid.paragraphs]
            + [cell.text for table in not_paid.tables for row in table.rows for cell in row.cells]
        )
        self.assertIn("Công an tỉnh Thái Bình", paid_text)
        self.assertEqual(paid.sections[0].orientation, WD_ORIENT.LANDSCAPE)
        self.assertEqual(paid.tables[0].style.name, "Table Grid")
        self.assertIsNotNone(paid.tables[0].rows[0]._tr.trPr)
        self.assertIn("tblHeader", paid.tables[0].rows[0]._tr.trPr.xml)
        self.assertIn("Cục Tổ chức cán bộ", not_paid_text)
        self.assertIn("Phụ lục: Các dòng chưa thể kết luận", not_paid_text)

    def test_api_returns_zip_and_summary_headers(self) -> None:
        response = TestClient(app).post(
            "/api/v1/organizations/batch",
            files={
                "file": (
                    "input.xlsx",
                    make_excel_input(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/zip")
        self.assertEqual(response.headers["x-batch-input-count"], "3")
        self.assertEqual(response.headers["x-batch-paid-count"], "1")
        self.assertEqual(response.headers["x-batch-not-paid-count"], "1")
        self.assertEqual(response.headers["x-batch-unresolved-count"], "1")
        with ZipFile(BytesIO(response.content)) as archive:
            self.assertEqual(len(archive.namelist()), 2)


if __name__ == "__main__":
    unittest.main()
