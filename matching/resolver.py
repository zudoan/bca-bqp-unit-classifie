"""Resolver orchestration for exact-first matching with fuzzy fallback."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from preprocessing.normalize import to_search_key
from preprocessing.validate import SearchInput

from .acronym_match import AcronymMatcher
from .alias_match import AliasMatcher
from .exact_match import ExactMatcher
from .fuzzy_match import FuzzyMatcher
from .models import (
    MatchCandidate,
    MatchResolution,
    MatchStatus,
    OrganizationRecord,
)
from .repository import OrganizationRepository


@dataclass(frozen=True, slots=True)
class MatchingConfig:
    strict_mode: bool = False
    enable_fuzzy: bool = True
    fuzzy_auto_resolve_threshold: float = 93.0
    fuzzy_candidate_threshold: float = 75.0
    fuzzy_min_score_gap: float = 5.0
    fuzzy_candidate_limit: int = 5


class OrganizationResolver:
    """Resolve a request to a canonical organization, never to BCA/BQP."""

    def __init__(
        self,
        repository: OrganizationRepository,
        config: MatchingConfig | None = None,
        acronym_matcher: AcronymMatcher | None = None,
    ) -> None:
        self.repository = repository
        self.config = config or MatchingConfig()
        self.exact_matcher = ExactMatcher(repository)
        self.alias_matcher = AliasMatcher(repository)
        self.fuzzy_matcher = FuzzyMatcher(repository)
        self.acronym_matcher = acronym_matcher

    def resolve(self, request: SearchInput) -> MatchResolution:
        """Run deterministic stages first, then conservative fuzzy retrieval."""

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

        if self.acronym_matcher is not None:
            acronym_matches = self.acronym_matcher.match(
                request.organization_name
            )
            if acronym_matches:
                return self._resolve_deterministic_group(
                    MatchStatus.ACRONYM_MATCH,
                    acronym_matches,
                    request,
                )

        if self.config.enable_fuzzy and not self.config.strict_mode:
            fuzzy_candidates = self.fuzzy_matcher.match(
                request.organization_name,
                province_name=request.province_name,
                organization_type_code=request.organization_type,
                candidate_threshold=self.config.fuzzy_candidate_threshold,
                limit=self.config.fuzzy_candidate_limit,
            )
            if fuzzy_candidates:
                top = fuzzy_candidates[0]
                runner_up_score = (
                    fuzzy_candidates[1].score
                    if len(fuzzy_candidates) > 1
                    else 0.0
                )
                if (
                    top.score >= self.config.fuzzy_auto_resolve_threshold
                    and top.score - runner_up_score
                    >= self.config.fuzzy_min_score_gap
                ):
                    return MatchResolution(
                        match_status=MatchStatus.FUZZY_MATCH,
                        organization=top.organization,
                        match_score=top.score,
                    )
                return MatchResolution(
                    match_status=MatchStatus.FUZZY_CANDIDATES,
                    candidates=fuzzy_candidates,
                    reason="FUZZY_REVIEW_REQUIRED",
                )

        return MatchResolution(
            match_status=MatchStatus.NOT_FOUND,
            reason="NO_MATCH",
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
