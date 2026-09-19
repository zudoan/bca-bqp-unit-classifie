"""Deterministic canonical-name matching stages."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from preprocessing.normalize import normalize_name, to_search_key

from .models import MatchStatus, OrganizationRecord
from .repository import OrganizationRepository


@dataclass(frozen=True, slots=True)
class DeterministicMatch:
    match_status: MatchStatus
    organizations: tuple[OrganizationRecord, ...]


class ExactMatcher:
    """Run exact canonical tiers in their required order."""

    def __init__(self, repository: OrganizationRepository) -> None:
        self.repository = repository

    def match_id(self, organization_id: str) -> OrganizationRecord | None:
        return self.repository.get_by_id(organization_id)

    def match_name(self, organization_name: str) -> DeterministicMatch | None:
        stages = (
            (
                MatchStatus.EXACT_NAME_MATCH,
                lambda: self.repository.find_by_exact_name(organization_name),
            ),
            (
                MatchStatus.NORMALIZED_MATCH,
                lambda: self.repository.find_by_normalized_name(
                    normalize_name(organization_name)
                ),
            ),
            (
                MatchStatus.SEARCH_KEY_MATCH,
                lambda: self.repository.find_by_search_key(
                    to_search_key(organization_name)
                ),
            ),
        )
        for status, find in stages:
            organizations = _deduplicate(find())
            if organizations:
                return DeterministicMatch(status, organizations)
        return None


def _deduplicate(
    organizations: Iterable[OrganizationRecord],
) -> tuple[OrganizationRecord, ...]:
    result: dict[str, OrganizationRecord] = {}
    for organization in organizations:
        result[organization.organization_id] = organization
    return tuple(result[key] for key in sorted(result))
