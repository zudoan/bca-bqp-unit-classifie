"""Safe PDF text extraction with a Gemini fallback for scanned documents."""

from __future__ import annotations

from dataclasses import dataclass
import base64
from io import BytesIO
import json
import os
import re
from typing import Any, Protocol, Sequence
from urllib.parse import quote

from preprocessing.normalize import to_search_key


MAX_PDF_PAGES = 50
MIN_DOCUMENT_TEXT_CHARS = 24
GEMINI_OCR_PROMPT = """Extract only organization or agency names from this PDF.
Return one array item for every occurrence, preserving document reading order.
Exclude headings, column titles, page numbers, signatures, dates, addresses, and explanatory text.
Keep each organization name exactly as written; do not translate, normalize, correct, or invent names.
If there are no organization names, return an empty array."""

_HEADER_KEYS = {
    "ten don vi",
    "ten to chuc",
    "don vi",
    "to chuc",
    "organization name",
    "organization_name",
    "org name",
    "ten",
    "name",
}
_DOCUMENT_HEADING_KEYS = {
    "danh sach",
    "danh sach don vi",
    "danh sach to chuc",
    "danh sach cac don vi",
    "cong hoa xa hoi chu nghia viet nam",
    "doc lap tu do hanh phuc",
    "stt",
}
_MARKDOWN_SEPARATOR = re.compile(r"^:?-{3,}:?$")
_LIST_PREFIX = re.compile(
    r"^\s*(?:(?:[-*•●▪◦])|(?:\d{1,5}[.)])|(?:\(\d{1,5}\)))\s*"
)
_PAGE_NUMBER = re.compile(r"^(?:trang\s+)?\d{1,4}(?:\s*/\s*\d{1,4})?$", re.I)


class PdfProcessingError(ValueError):
    """Raised when a PDF cannot be validated or interpreted as an org list."""


class OcrConfigurationError(PdfProcessingError):
    """Raised when a scanned PDF needs OCR but Gemini is not configured."""


class OcrUpstreamError(PdfProcessingError):
    """Raised when the configured Gemini service fails."""


@dataclass(frozen=True, slots=True)
class PdfOrganization:
    source: str
    source_row: int
    organization_name: str


@dataclass(frozen=True, slots=True)
class PdfExtraction:
    organizations: tuple[PdfOrganization, ...]
    input_mode: str


class OcrProvider(Protocol):
    def extract_text(self, content: bytes) -> str:
        """Return OCR text for a complete PDF."""


class GeminiOcrProvider:
    """Gemini Developer API client for scanned PDF organization extraction."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = "gemini-2.5-flash",
        api_url: str = "https://generativelanguage.googleapis.com/v1beta",
        timeout: int = 300,
        max_output_tokens: int = 32_768,
    ) -> None:
        self.api_key = (api_key or "").strip() or None
        self.model = model.strip().removeprefix("models/") or "gemini-2.5-flash"
        self.api_url = api_url.strip().rstrip("/")
        self.timeout = timeout
        self.max_output_tokens = max(256, min(max_output_tokens, 65_536))

    @classmethod
    def from_environment(cls) -> "GeminiOcrProvider":
        raw_timeout = os.getenv("GEMINI_TIMEOUT", "300")
        raw_max_tokens = os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "32768")
        try:
            timeout = max(30, min(int(raw_timeout), 900))
        except ValueError:
            timeout = 300
        try:
            max_output_tokens = max(256, min(int(raw_max_tokens), 65_536))
        except ValueError:
            max_output_tokens = 32_768
        return cls(
            api_key=os.getenv("GEMINI_API_KEY"),
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            api_url=os.getenv(
                "GEMINI_API_URL",
                "https://generativelanguage.googleapis.com/v1beta",
            ),
            timeout=timeout,
            max_output_tokens=max_output_tokens,
        )

    def extract_text(self, content: bytes) -> str:
        if not self.api_key:
            raise OcrConfigurationError(
                "PDF scan cần Gemini OCR nhưng GEMINI_API_KEY chưa được cấu hình."
            )
        import requests

        endpoint = _gemini_generate_content_url(self.api_url, self.model)
        payload = {
            # GenerateContent does not store requests by default; make that intent
            # explicit for documents that can contain sensitive organization data.
            "store": False,
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"inline_data": {
                            "mime_type": "application/pdf",
                            "data": base64.b64encode(content).decode("ascii"),
                        }},
                        {"text": GEMINI_OCR_PROMPT},
                    ],
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "maxOutputTokens": self.max_output_tokens,
                # OCR/list extraction does not need chain-of-thought. Disabling it
                # also prevents reasoning parts from consuming the output budget.
                "thinkingConfig": {"thinkingBudget": 0},
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
        }
        try:
            response = requests.post(
                endpoint,
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": self.api_key,
                },
                json=payload,
                timeout=self.timeout,
            )
        except requests.RequestException as error:
            raise OcrUpstreamError(_describe_gemini_error(error)) from error

        if response.status_code >= 400:
            raise OcrUpstreamError(
                _describe_gemini_error(response.text, response.status_code)
            )
        try:
            data = response.json()
        except ValueError as error:
            raise OcrUpstreamError("Gemini trả về HTTP 200 nhưng body không phải JSON.") from error

        candidate = _gemini_candidate(data)
        finish_reason = str(candidate.get("finishReason") or "").upper()
        response_id = str(data.get("responseId") or "").strip()
        if finish_reason == "MAX_TOKENS":
            raise OcrUpstreamError(
                "Kết quả OCR quá dài và bị Gemini cắt (MAX_TOKENS). "
                "Hãy chia PDF thành các file nhỏ hơn hoặc tăng GEMINI_MAX_OUTPUT_TOKENS."
            )
        if finish_reason in {
            "SAFETY",
            "RECITATION",
            "BLOCKLIST",
            "PROHIBITED_CONTENT",
            "SPII",
            "IMAGE_SAFETY",
        }:
            raise OcrUpstreamError(
                f"Gemini chặn kết quả OCR do chính sách ({finish_reason})."
            )

        content = candidate.get("content")
        parts = content.get("parts") if isinstance(content, dict) else None
        if not isinstance(parts, list):
            suffix = f" Mã phản hồi: {response_id}." if response_id else ""
            raise OcrUpstreamError(
                "Gemini không trả về phần nội dung OCR." + suffix
            )
        result_text = "".join(
            part.get("text", "")
            for part in parts
            if isinstance(part, dict) and not part.get("thought")
        ).strip()
        try:
            names = _parse_organization_names(result_text)
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            suffix = f" Mã phản hồi: {response_id}." if response_id else ""
            raise OcrUpstreamError(
                "Gemini trả về nội dung OCR không đúng định dạng danh sách JSON."
                + suffix
            ) from error
        return "\n".join(name.strip() for name in names if name.strip())


def _gemini_candidate(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise OcrUpstreamError("Gemini trả về cấu trúc phản hồi không hợp lệ.")
    candidates = data.get("candidates")
    if isinstance(candidates, list) and candidates and isinstance(candidates[0], dict):
        return candidates[0]
    prompt_feedback = data.get("promptFeedback")
    block_reason = (
        str(prompt_feedback.get("blockReason") or "").upper()
        if isinstance(prompt_feedback, dict)
        else ""
    )
    if block_reason:
        raise OcrUpstreamError(
            f"Gemini chặn tài liệu trước khi OCR ({block_reason})."
        )
    raise OcrUpstreamError("Gemini không trả về ứng viên OCR.")


def _parse_organization_names(result_text: str) -> list[str]:
    """Parse structured output while tolerating harmless Markdown wrappers."""

    text = result_text.strip().lstrip("\ufeff")
    if not text:
        return []
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, count=1, flags=re.I)
        text = re.sub(r"\s*```$", "", text, count=1).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        array_start = text.find("[")
        if array_start < 0:
            raise
        parsed, _ = json.JSONDecoder().raw_decode(text[array_start:])

    if isinstance(parsed, dict):
        for key in ("organizations", "organization_names", "names", "items"):
            if isinstance(parsed.get(key), list):
                parsed = parsed[key]
                break
    if not isinstance(parsed, list):
        raise ValueError("OCR result is not a list")

    names: list[str] = []
    for item in parsed:
        if isinstance(item, str):
            names.append(item)
            continue
        if isinstance(item, dict):
            value = next(
                (
                    item.get(key)
                    for key in ("organization_name", "organization", "name", "text")
                    if isinstance(item.get(key), str)
                ),
                None,
            )
            if value is not None:
                names.append(value)
                continue
        raise ValueError("OCR list contains an unsupported item")
    return names


def _gemini_generate_content_url(api_url: str, model: str) -> str:
    if api_url.endswith(":generateContent"):
        return api_url
    encoded_model = quote(model.removeprefix("models/"), safe="-._")
    return f"{api_url.rstrip('/')}/models/{encoded_model}:generateContent"


def _describe_gemini_error(error: Any, status_code: int | None = None) -> str:
    """Translate upstream failures without exposing credentials or document data."""

    text = str(error)
    lowered = text.lower()
    if any(marker in lowered for marker in ("failed to resolve", "name resolution", "gaierror")):
        return "Không phân giải được hostname Gemini API. Hãy kiểm tra kết nối Internet."
    if any(marker in lowered for marker in ("connection refused", "max retries exceeded", "connectionpool")):
        return "Không thể kết nối tới Gemini API. Hãy kiểm tra Internet hoặc proxy/firewall."
    if any(marker in lowered for marker in ("timed out", "timeout")):
        return "Gemini phản hồi quá thời gian. Hãy thử lại hoặc tăng GEMINI_TIMEOUT."
    if status_code in {401, 403}:
        return "Gemini từ chối API key. Hãy kiểm tra GEMINI_API_KEY và quyền của Google AI Studio project."
    if status_code == 404:
        return "Không tìm thấy model Gemini. Hãy kiểm tra GEMINI_MODEL."
    if status_code == 429 or any(marker in lowered for marker in ("429", "rate limit")):
        return "Gemini đã vượt quota hoặc giới hạn tần suất. Hãy kiểm tra quota Google AI Studio."
    if status_code == 400:
        return "Gemini từ chối tài liệu hoặc cấu hình request OCR."
    if status_code:
        return f"Gemini OCR trả về HTTP {status_code}."
    return "Gemini không thể nhận dạng tài liệu."


def read_pdf_organizations(
    content: bytes,
    column_name: str | None = None,
    ocr_provider: OcrProvider | None = None,
) -> PdfExtraction:
    """Extract organization rows from a text PDF or scanned PDF."""

    page_texts = _validate_and_extract_page_text(content)
    meaningful_chars = sum(
        1 for text in page_texts for character in text if character.isalnum()
    )
    text_pages = sum(
        1 for text in page_texts if sum(character.isalnum() for character in text) >= 8
    )
    enough_text = meaningful_chars >= max(
        MIN_DOCUMENT_TEXT_CHARS, len(page_texts) * 8
    ) and text_pages >= max(1, (len(page_texts) + 1) // 2)

    if enough_text:
        organizations = _extract_digital_pdf(content, page_texts, column_name)
        return PdfExtraction(tuple(organizations), "pdf-text")

    provider = ocr_provider or GeminiOcrProvider.from_environment()
    ocr_text = provider.extract_text(content)
    organizations = _extract_markdown_or_text(ocr_text, column_name, "Gemini 2.5 Flash")
    return PdfExtraction(tuple(organizations), "gemini-ocr")


def _validate_and_extract_page_text(content: bytes) -> list[str]:
    if not content.startswith(b"%PDF-"):
        raise PdfProcessingError("File không có chữ ký PDF hợp lệ.")
    try:
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(content), strict=True)
        if reader.is_encrypted:
            raise PdfProcessingError("Không hỗ trợ PDF được mã hóa hoặc đặt mật khẩu.")
        page_count = len(reader.pages)
        if page_count == 0:
            raise PdfProcessingError("PDF không có trang nội dung.")
        if page_count > MAX_PDF_PAGES:
            raise PdfProcessingError(
                f"PDF có {page_count} trang; giới hạn mỗi lần xử lý là {MAX_PDF_PAGES} trang."
            )
        return [(page.extract_text() or "") for page in reader.pages]
    except PdfProcessingError:
        raise
    except Exception as error:
        raise PdfProcessingError("Không thể đọc PDF; file có thể bị hỏng.") from error


def _extract_digital_pdf(
    content: bytes, page_texts: Sequence[str], column_name: str | None
) -> list[PdfOrganization]:
    table_rows: list[PdfOrganization] = []
    table_errors: list[PdfProcessingError] = []
    try:
        import pdfplumber

        with pdfplumber.open(BytesIO(content)) as document:
            for page_number, page in enumerate(document.pages, start=1):
                for table_number, table in enumerate(page.extract_tables(), start=1):
                    if not table:
                        continue
                    try:
                        table_rows.extend(
                            _extract_table_rows(
                                table,
                                f"Trang {page_number}, bảng {table_number}",
                                column_name,
                            )
                        )
                    except PdfProcessingError as error:
                        table_errors.append(error)
    except Exception:
        # pypdf text remains a safe fallback when a page has no table geometry.
        pass

    if table_rows:
        return table_rows
    if column_name and table_errors:
        raise table_errors[0]

    joined_text = "\n".join(page_texts)
    return _extract_markdown_or_text(joined_text, column_name, "PDF")


def _extract_markdown_or_text(
    text: str, column_name: str | None, source: str
) -> list[PdfOrganization]:
    lines = text.replace("\x00", "").splitlines()
    tables = _markdown_tables(lines)
    table_rows: list[PdfOrganization] = []
    table_errors: list[PdfProcessingError] = []
    for table_index, rows in enumerate(tables, start=1):
        try:
            table_rows.extend(
                _extract_table_rows(rows, f"{source}, bảng {table_index}", column_name)
            )
        except PdfProcessingError as error:
            table_errors.append(error)
    if table_rows:
        return table_rows
    if column_name and table_errors:
        raise table_errors[0]

    extracted: list[PdfOrganization] = []
    for line_number, raw_line in enumerate(lines, start=1):
        name = _clean_plain_line(raw_line)
        if not name:
            continue
        extracted.append(PdfOrganization(source, line_number, name))
    return extracted


def _markdown_tables(lines: Sequence[str]) -> list[list[list[str]]]:
    tables: list[list[list[str]]] = []
    current: list[list[str]] = []
    for raw_line in lines:
        stripped = raw_line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if cells and all(_MARKDOWN_SEPARATOR.match(cell) for cell in cells):
                continue
            current.append(cells)
        elif current:
            if len(current) >= 2:
                tables.append(current)
            current = []
    if len(current) >= 2:
        tables.append(current)
    return tables


def _extract_table_rows(
    rows: Sequence[Sequence[Any]], source: str, column_name: str | None
) -> list[PdfOrganization]:
    requested_key = _key(column_name) if column_name else None
    header_index: int | None = None
    column_index: int | None = None
    for row_index, row in enumerate(rows[:25]):
        for candidate_index, value in enumerate(row):
            key = _key(value)
            if requested_key and key == requested_key:
                header_index, column_index = row_index, candidate_index
                break
            if not requested_key and key in _HEADER_KEYS:
                header_index, column_index = row_index, candidate_index
                break
        if column_index is not None:
            break

    if column_index is None:
        populated = {
            index
            for row in rows
            for index, value in enumerate(row)
            if index < len(row) and _clean_cell(value)
        }
        if requested_key:
            raise PdfProcessingError(
                f"Không tìm thấy cột “{column_name}” trong {source}."
            )
        if len(populated) != 1:
            raise PdfProcessingError(
                f"Không xác định được cột tên đơn vị trong {source}."
            )
        column_index = next(iter(populated))
        header_index = 0 if _key(rows[0][column_index]) in _HEADER_KEYS else -1

    start = (header_index + 1) if header_index is not None else 0
    extracted: list[PdfOrganization] = []
    for row_index, row in enumerate(rows[start:], start=start):
        value = row[column_index] if column_index < len(row) else None
        name = _clean_cell(value)
        if name and _key(name) not in _HEADER_KEYS:
            extracted.append(PdfOrganization(source, row_index + 1, name))
    return extracted


def _clean_plain_line(raw_line: str) -> str:
    line = raw_line.strip().strip("|").strip()
    line = re.sub(r"^#{1,6}\s*", "", line)
    line = _LIST_PREFIX.sub("", line).strip()
    if not line or len(line) > 512 or _PAGE_NUMBER.match(line):
        return ""
    key = _key(line)
    if not key or key in _HEADER_KEYS or key in _DOCUMENT_HEADING_KEYS:
        return ""
    if all(character in "-_=.: " for character in line):
        return ""
    return line


def _key(value: Any) -> str:
    text = _clean_cell(value)
    return to_search_key(text).replace("_", " ").strip() if text else ""


def _clean_cell(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\x00", "").split())[:512]
