"""Resolver orchestration for strict deterministic entity matching."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from preprocessing.normalize import to_search_key
from preprocessing.validate import SearchInput

from .alias_match import AliasMatcher
from .exact_match import ExactMatcher
from .models import (
    MatchCandidate,
    MatchResolution,
    MatchStatus,
    OrganizationRecord,
)
from .repository import OrganizationRepository


@dataclass(frozen=True, slots=True)
class MatchingConfig:
    strict_mode: bool = True


class OrganizationResolver:
    """Resolve a request to a canonical organization, never to BCA/BQP."""

    def __init__(
        self,
        repository: OrganizationRepository,
        config: MatchingConfig | None = None,
    ) -> None:
        self.repository = repository
        self.config = config or MatchingConfig()
        self.exact_matcher = ExactMatcher(repository)
        self.alias_matcher = AliasMatcher(repository)

    def resolve(self, request: SearchInput) -> MatchResolution:
        """Run ID -> name -> normalized -> key -> alias stages (Strict Deterministic)."""

        if request.organization_id:
            organization = self.exact_matcher.match_id(request.organization_id)
            if organization is not None:
                return self._resolve_deterministic_group(
                    MatchStatus.EXACT_ID_MATCH,
                    (organization,),
                    request,
                )

        if not request.organization_name:
            return MatchResolution(
                match_status=MatchStatus.NOT_FOUND,
                reason="ORGANIZATION_ID_NOT_FOUND",
            )

        deterministic = self.exact_matcher.match_name(request.organization_name)
        if deterministic is not None:
            return self._resolve_deterministic_group(
                deterministic.match_status,
                deterministic.organizations,
                request,
            )

        alias_matches = self.alias_matcher.match(request.organization_name)
        if alias_matches:
            return self._resolve_deterministic_group(
                MatchStatus.ALIAS_MATCH,
                alias_matches,
                request,
            )

        return MatchResolution(
            match_status=MatchStatus.NOT_FOUND,
            reason="NO_EXACT_MATCH",
        )

    def _resolve_deterministic_group(
        self,
        status: MatchStatus,
        organizations: Sequence[OrganizationRecord],
        request: SearchInput,
    ) -> MatchResolution:
        candidates = self._apply_context(organizations, request)
        if len(candidates) == 1:
            return MatchResolution(
                match_status=status,
                organization=candidates[0],
                match_score=100.0,
            )
        if not candidates:
            # A deterministic identity existed but contradicted explicit
            # context.  Do not silently ignore the context or fuzzy-match a
            # different organization.
            return MatchResolution(
                match_status=MatchStatus.NOT_FOUND,
                reason="DETERMINISTIC_MATCH_CONTEXT_MISMATCH",
            )
        return MatchResolution(
            match_status=MatchStatus.AMBIGUOUS_MATCH,
            candidates=tuple(
                MatchCandidate(
                    organization=organization,
                    score=100.0,
                    matched_on=status.value,
                    matched_value=organization.organization_name,
                )
                for organization in candidates
            ),
            reason="MULTIPLE_DETERMINISTIC_MATCHES",
        )

    @staticmethod
    def _apply_context(
        organizations: Sequence[OrganizationRecord],
        request: SearchInput,
    ) -> tuple[OrganizationRecord, ...]:
        """Disambiguate in the Version 1 order: province, then type."""

        candidates = list(organizations)
        if request.province_name:
            province_key = to_search_key(request.province_name)
            candidates = [
                organization
                for organization in candidates
                if to_search_key(organization.province_name or "") == province_key
            ]
        if request.organization_type:
            type_key = request.organization_type.strip().upper()
            candidates = [
                organization
                for organization in candidates
                if organization.organization_type_code.strip().upper() == type_key
            ]
        candidates.sort(key=lambda organization: organization.organization_id)
        return tuple(candidates)
