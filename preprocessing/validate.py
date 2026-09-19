"""Validation of the public Version 1 search contract."""

from __future__ import annotations

from dataclasses import dataclass

MAX_ORGANIZATION_ID_LENGTH = 128
MAX_ORGANIZATION_NAME_LENGTH = 512
MAX_CONTEXT_LENGTH = 128


class InputValidationError(ValueError):
    """Raised when a search request cannot safely enter the matching pipeline."""

    def __init__(self, errors: list[str] | tuple[str, ...]):
        self.errors = tuple(errors)
        super().__init__("; ".join(self.errors))


@dataclass(frozen=True, slots=True)
class SearchInput:
    organization_id: str | None = None
    organization_name: str | None = None
    province_name: str | None = None
    organization_type: str | None = None


def _clean_optional_string(
    value: object,
    field_name: str,
    maximum_length: int,
    errors: list[str],
    preserve_outer_whitespace: bool = False,
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        errors.append(f"{field_name} must be a string")
        return None
    if "\x00" in value:
        errors.append(f"{field_name} must not contain NUL characters")
        return None
    stripped = value.strip()
    if not stripped:
        return None
    cleaned = value if preserve_outer_whitespace else stripped
    if len(cleaned) > maximum_length:
        errors.append(
            f"{field_name} must not exceed {maximum_length} characters"
        )
    return cleaned


def validate_search_input(
    organization_id: object = None,
    organization_name: object = None,
    province_name: object = None,
    organization_type: object = None,
) -> SearchInput:
    """Validate and minimally clean a search request.

    Original name casing and punctuation are retained so the exact-name stage
    remains a true exact match.  Normalized forms are produced later by the
    resolver.
    """

    errors: list[str] = []
    clean_id = _clean_optional_string(
        organization_id,
        "organization_id",
        MAX_ORGANIZATION_ID_LENGTH,
        errors,
    )
    clean_name = _clean_optional_string(
        organization_name,
        "organization_name",
        MAX_ORGANIZATION_NAME_LENGTH,
        errors,
        preserve_outer_whitespace=True,
    )
    clean_province = _clean_optional_string(
        province_name,
        "province_name",
        MAX_CONTEXT_LENGTH,
        errors,
    )
    clean_type = _clean_optional_string(
        organization_type,
        "organization_type",
        MAX_CONTEXT_LENGTH,
        errors,
    )

    if clean_id is None and clean_name is None:
        errors.append("organization_id or organization_name is required")
    if errors:
        raise InputValidationError(errors)

    return SearchInput(
        organization_id=clean_id,
        organization_name=clean_name,
        province_name=clean_province,
        organization_type=clean_type.upper() if clean_type else None,
    )
