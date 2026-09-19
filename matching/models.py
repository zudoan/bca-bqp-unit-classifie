"""Domain objects shared by the matching layers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class MatchStatus(str, Enum):
    EXACT_ID_MATCH = "EXACT_ID_MATCH"
    EXACT_NAME_MATCH = "EXACT_NAME_MATCH"
    NORMALIZED_MATCH = "NORMALIZED_MATCH"
    SEARCH_KEY_MATCH = "SEARCH_KEY_MATCH"
    ALIAS_MATCH = "ALIAS_MATCH"
    FUZZY_CANDIDATES = "FUZZY_CANDIDATES"
    FUZZY_MATCH = "FUZZY_MATCH"  # Reserved for a later, benchmarked version.
    AMBIGUOUS_MATCH = "AMBIGUOUS_MATCH"
    NOT_FOUND = "NOT_FOUND"
    INVALID_INPUT = "INVALID_INPUT"


DETERMINISTIC_MATCH_STATUSES = frozenset(
    {
        MatchStatus.EXACT_ID_MATCH,
        MatchStatus.EXACT_NAME_MATCH,
        MatchStatus.NORMALIZED_MATCH,
        MatchStatus.SEARCH_KEY_MATCH,
        MatchStatus.ALIAS_MATCH,
    }
)


@dataclass(frozen=True, slots=True)
class OrganizationRecord:
    """Matching-safe organization view; deliberately excludes management."""

    organization_id: str
    organization_name: str
    normalized_name: str
    search_key: str
    organization_type_code: str
    organization_level: str | None = None
    parent_organization_id: str | None = None
    province_name: str | None = None

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> "OrganizationRecord":
        """Build from master-table or source-CSV column names."""

        normalized_name = row.get("normalized_name")
        if normalized_name is None:
            normalized_name = row.get("organization_name_normalized")
        search_key = row.get("search_key")
        if search_key is None:
            search_key = row.get("organization_name_search_key")
        return cls(
            organization_id=str(row["organization_id"]),
            organization_name=str(row["organization_name"]),
            normalized_name=str(normalized_name or ""),
            search_key=str(search_key or ""),
            organization_type_code=str(row["organization_type_code"]),
            organization_level=_optional_string(row.get("organization_level")),
            parent_organization_id=_optional_string(
                row.get("parent_organization_id")
            ),
            province_name=_optional_string(row.get("province_name")),
        )


@dataclass(frozen=True, slots=True)
class AliasRecord:
    organization_id: str
    alias_name: str
    normalized_alias: str
    alias_search_key: str
    alias_type: str = "COMMON_NAME"
    alias_id: int | str | None = None

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> "AliasRecord":
        return cls(
            organization_id=str(row["organization_id"]),
            alias_name=str(row["alias_name"]),
            normalized_alias=str(row["normalized_alias"]),
            alias_search_key=str(row["alias_search_key"]),
            alias_type=str(row.get("alias_type") or "COMMON_NAME"),
            alias_id=row.get("alias_id"),
        )


@dataclass(frozen=True, slots=True)
class MatchCandidate:
    organization: OrganizationRecord
    score: float
    matched_on: str
    matched_value: str | None = None


@dataclass(frozen=True, slots=True)
class MatchResolution:
    """Resolver output before management lookup."""

    match_status: MatchStatus
    organization: OrganizationRecord | None = None
    match_score: float | None = None
    candidates: tuple[MatchCandidate, ...] = field(default_factory=tuple)
    reason: str | None = None

    @property
    def is_resolved(self) -> bool:
        return (
            self.match_status in DETERMINISTIC_MATCH_STATUSES
            and self.organization is not None
        )


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None
