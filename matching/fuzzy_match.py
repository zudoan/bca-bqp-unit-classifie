"""Conservative fuzzy candidate retrieval for organization names."""

from __future__ import annotations

from collections.abc import Sequence

from rapidfuzz import fuzz

from preprocessing.normalize import to_search_key

from .models import MatchCandidate
from .repository import OrganizationRepository


class FuzzyMatcher:
    """Rank canonical names and registered aliases without using outcome data."""

    def __init__(self, repository: OrganizationRepository) -> None:
        self.repository = repository

    def match(
        self,
        organization_name: str,
        *,
        province_name: str | None = None,
        organization_type_code: str | None = None,
        candidate_threshold: float = 75.0,
        limit: int = 5,
    ) -> tuple[MatchCandidate, ...]:
        query_key = to_search_key(organization_name)
        # Very short strings produce unsafe partial matches.
        if len(query_key) < 5:
            return ()

        organizations = self.repository.list_candidates(
            province_name=province_name,
            organization_type_code=organization_type_code,
        )
        aliases = self.repository.list_aliases(
            [organization.organization_id for organization in organizations]
        )
        aliases_by_id: dict[str, list[str]] = {}
        for alias in aliases:
            aliases_by_id.setdefault(alias.organization_id, []).append(
                alias.alias_search_key
            )

        ranked: list[MatchCandidate] = []
        for organization in organizations:
            best_score = float(fuzz.WRatio(query_key, organization.search_key))
            matched_on = "FUZZY_CANONICAL_NAME"
            matched_value = organization.organization_name
            for alias_key in aliases_by_id.get(organization.organization_id, ()):
                alias_score = float(fuzz.WRatio(query_key, alias_key))
                if alias_score > best_score:
                    best_score = alias_score
                    matched_on = "FUZZY_ALIAS"
                    matched_value = alias_key
            if best_score >= candidate_threshold:
                ranked.append(
                    MatchCandidate(
                        organization=organization,
                        score=best_score,
                        matched_on=matched_on,
                        matched_value=matched_value,
                    )
                )

        ranked.sort(
            key=lambda candidate: (
                -candidate.score,
                candidate.organization.organization_id,
            )
        )
        return tuple(ranked[:limit])
